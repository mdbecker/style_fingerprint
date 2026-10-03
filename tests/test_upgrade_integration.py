"""Observable integration behavior for hierarchical scoring and frozen builds."""
import json
import numpy as np


def test_given_identical_style_when_lengths_differ_then_predictor_vector_is_identical():
    from style_fingerprint.model import StyleFingerprint
    signals = dict(authorship_embedding=.7, stylometry=.6, char_ngram=.5)
    from style_fingerprint.features import extract_features
    features = extract_features('I like careful experiments. We compare their results.')
    reference = {'features': [features, features]}
    a = StyleFingerprint._comparison_features(signals, features, {'a': .6, 'b': .8}, reference, 50, 1)
    b = StyleFingerprint._comparison_features(signals, features, {'a': .6, 'b': .8}, reference, 900, 5)
    assert a == b
    assert not {'usable_words', 'candidate_passages', 'raw_character_count', 'generated_views'} & a.keys()


def test_given_candidate_when_scored_then_decision_and_thresholds_are_public(fingerprint):
    result = fingerprint.score('I like careful experiments. We compare their results.', explain=False)
    assert result.decision == 'INCONCLUSIVE_OR_MISMATCH'
    assert result.match_threshold is None
    assert result.mismatch_threshold is None
    assert result.component_scores['character'] == result.component_scores['char_ngram']


def test_given_many_candidate_passages_when_retrieved_then_only_three_unique_analogues(fingerprint):
    result = fingerprint.score(fingerprint.documents[0].clean_text, explain=False)
    keys = [(p['document_id'], p['passage_id']) for p in result.nearest_reference_passages]
    assert len(keys) <= 3
    assert len(keys) == len(set(keys))


def test_given_evaluation_when_production_refits_then_choices_and_report_are_frozen(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    bank = tmp_path / 'bank'
    evaluation = StyleFingerprint.build(corpus, bank, holdout_fraction=0, build_mode='evaluation')
    frozen = json.loads((bank / 'evaluation_config.json').read_text())
    report = (bank / 'evaluation.json').read_bytes()
    production = StyleFingerprint.build(corpus, bank, holdout_fraction=0, build_mode='production')
    assert production.manifest['build_mode'] == 'production'
    assert production.manifest['evaluation_configuration'] == frozen
    assert (bank / 'evaluation.json').read_bytes() == report
    assert {'model_type','calibration_type','match_threshold','mismatch_threshold'} <= production.manifest.keys()
    assert production.manifest['production_build_timestamp']
    assert evaluation.manifest['evaluation_timestamp']


def test_given_sealed_manifest_when_production_builds_then_reserved_roots_stay_excluded(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    manifest = tmp_path / 'sealed.json'
    manifest.write_text(json.dumps({'holdout_v2': ['post-0.markdown']}))
    fp = StyleFingerprint.build(corpus, tmp_path/'bank', holdout_fraction=0,
                                holdout_manifest=manifest, build_mode='production')
    assert 'post-0.markdown' not in fp.manifest['historical_document_ids']
    assert 'post-0.markdown' not in {p.document_id for p in fp.passages}
    assert fp.manifest['sealed_holdout_ids'] == ['post-0.markdown']


def test_given_no_frozen_config_when_cli_builds_then_automatic_evaluation_is_explicit(corpus, encoder, tmp_path, capsys):
    from style_fingerprint.cli import main
    assert main(['build', '--corpus', str(corpus), '--no-holdout', '--artifacts', str(tmp_path/'bank')]) == 0
    output = capsys.readouterr().out
    assert 'No frozen evaluation configuration' in output
    assert json.loads((tmp_path/'bank'/'manifest.json').read_text())['build_mode'] == 'production'


def test_given_new_corpus_when_cli_evaluates_then_frozen_configuration_is_created(corpus, encoder, tmp_path):
    from style_fingerprint.cli import main
    assert main(['evaluate','--corpus',str(corpus),'--no-holdout','--artifacts',str(tmp_path/'bank'),'--json']) == 0
    assert (tmp_path/'bank'/'evaluation_config.json').exists()


def test_given_supervised_evaluation_when_holdout_is_scored_then_uses_frozen_threshold(encoder, tmp_path):
    from test_holdout_pipeline import inputs
    from style_fingerprint import StyleFingerprint
    fp = StyleFingerprint.build(inputs(tmp_path), tmp_path/'bank', holdout_fraction=.2)
    assert fp.evaluation['holdout']['threshold'] == fp.manifest['match_threshold']
    assert fp.evaluation['holdout']['threshold_policy'] == 'Frozen grouped development OOF threshold'
    assert all('decision' in row and 'raw_margin' in row and 'raw_component_scores' in row for row in fp.evaluation['holdout']['documents'])
    for row in fp.evaluation['holdout']['documents']:
        if not row['label']:
            diagnostic = next(r for r in fp.evaluation['negative_diagnostics'] if r['root_document_id'] == row['root_document_id'])
            assert diagnostic['embedding'] == row['raw_component_scores']['authorship_embedding'] * 100


def test_given_supervised_roots_when_saved_then_prediction_table_has_each_root_once(corpus, encoder, tmp_path):
    from test_supervised import negatives
    from style_fingerprint import StyleFingerprint
    import pandas as pd
    negatives(tmp_path/'negative_posts', 12)
    fp = StyleFingerprint.build(corpus, tmp_path/'bank', holdout_fraction=0)
    rows = pd.read_parquet(tmp_path/'bank'/'evaluation_predictions.parquet')
    assert set(rows['root_document_id']) == {d.root_document_id for d in fp.documents}
    assert rows['root_document_id'].is_unique
    assert {'split','view_count','label','score','raw_margin','decision','embedding_score','stylometry_score','character_score'} <= set(rows)
    assert 'text' not in rows and 'clean_text' not in rows


def test_given_multiview_candidate_when_scored_then_margin_is_median_of_view_margins(corpus, encoder, tmp_path):
    from test_supervised import negatives
    from style_fingerprint import StyleFingerprint
    from style_fingerprint.corpus import make_training_views, chunk_text, word_count
    negatives(tmp_path/'negative_posts', 12)
    fp = StyleFingerprint.build(corpus, tmp_path/'bank', holdout_fraction=0)
    text = '\n\n'.join(('I compare careful experiments because clear observations reveal useful conclusions. '*40)+f' Ending {i}.' for i in range(4))
    margins = []
    for view in make_training_views(text, 'candidate', seed=fp.config.seed):
        passages = chunk_text(view.clean_text, view.document_id, root_document_id='candidate')
        signals, features, scores, ref = fp._compare(view.clean_text, view.clean_text, passages, fp._embed(passages), fp.manifest['historical_document_ids'])
        _, margin, _ = fp._supervised_score(signals, features, scores, ref, word_count(view.clean_text), len(passages))
        margins.append(margin)
    result = fp.score(text, explain=False)
    assert len(margins) > 1
    assert result.raw_score == np.median(margins)
    assert result.diagnostics['view_margin_summary']['median'] == result.raw_score


def test_given_sealed_roots_when_evaluation_is_repeated_then_designation_persists(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    sealed = tmp_path/'sealed.json'
    sealed.write_text(json.dumps({'holdout_v2':['post-0.markdown']}))
    bank = tmp_path/'bank'
    StyleFingerprint.build(corpus, bank, holdout_fraction=0, holdout_manifest=sealed)
    repeated = StyleFingerprint.build(corpus, bank, holdout_fraction=0)
    assert 'post-0.markdown' not in repeated.manifest['historical_document_ids']


def test_given_incompatible_frozen_segmentation_when_production_builds_then_fails(corpus, encoder, tmp_path):
    import pytest
    from style_fingerprint import StyleFingerprint
    bank = tmp_path/'bank'
    StyleFingerprint.build(corpus, bank, holdout_fraction=0)
    path = bank/'evaluation_config.json'
    frozen = json.loads(path.read_text())
    frozen['segmentation']['maximum'] = 999
    path.write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match='segmentation|configuration'):
        StyleFingerprint.build(corpus, bank, holdout_fraction=0, build_mode='production')


def test_given_frozen_evaluation_when_production_includes_consumed_holdout_then_report_and_choices_stay_frozen(encoder, tmp_path):
    from test_holdout_pipeline import inputs
    from style_fingerprint import StyleFingerprint
    root=inputs(tmp_path); bank=tmp_path/'bank'
    evaluation=StyleFingerprint.build(root, bank)
    held=set(evaluation.manifest['holdout_split']['holdout_document_ids'])
    frozen=json.loads((bank/'evaluation_config.json').read_text())
    report=(bank/'report.html').read_bytes()
    predictions=(bank/'evaluation_predictions.parquet').read_bytes()
    production=StyleFingerprint.build(root, bank, build_mode='production')
    assert held <= {d.document_id for d in production.documents}
    assert production.manifest['evaluation_configuration'] == frozen
    assert production.verifier['kind'] == frozen['selected_model']
    assert production.manifest['match_threshold'] == frozen['match_threshold']
    assert (bank/'report.html').read_bytes() == report
    assert (bank/'evaluation_predictions.parquet').read_bytes() == predictions


def test_given_insufficient_remaining_negatives_when_production_refits_then_requires_reevaluation(corpus, encoder, tmp_path):
    import pytest
    from test_supervised import negatives
    from style_fingerprint import StyleFingerprint
    root=tmp_path/'negative_posts'; negatives(root,12)
    bank=tmp_path/'bank'
    StyleFingerprint.build(corpus, bank, holdout_fraction=0)
    for path in list(root.glob('*.md'))[:3]:
        path.unlink()
    with pytest.raises(ValueError, match='eligib|negative|evaluation'):
        StyleFingerprint.build(corpus, bank, holdout_fraction=0, build_mode='production')


def test_given_saved_email_source_when_evaluation_excludes_it_then_override_is_honored(corpus, encoder, tmp_path, capsys):
    from style_fingerprint.cli import main
    work=tmp_path/'work_corpus';work.mkdir()
    (work/'invented.txt').write_text('I carefully reviewed these invented observations and shared the findings with colleagues.')
    bank=tmp_path/'bank'
    assert main(['evaluate','--corpus',str(corpus),'--no-holdout','--artifacts',str(bank)]) == 0
    capsys.readouterr()
    assert main(['evaluate','--no-work-corpus','--artifacts',str(bank),'--json']) == 0
    capsys.readouterr()
    manifest=json.loads((bank/'manifest.json').read_text())
    assert not any(doc.startswith('work/') for doc in manifest['historical_document_ids'])


def test_given_reference_fallback_when_holdout_is_evaluated_then_no_holdout_threshold_is_selected(encoder, tmp_path):
    from test_holdout_pipeline import inputs
    from style_fingerprint import StyleFingerprint
    root=inputs(tmp_path)
    for path in list((tmp_path/'negative_posts').glob('*.md'))[8:]:
        path.unlink()
    fp=StyleFingerprint.build(root, tmp_path/'bank')
    assert fp.verifier is None
    report=fp.evaluation['holdout']
    assert report['threshold'] is None
    assert report['metrics']['match_threshold'] is None
    assert report['metrics']['false_positive_rate'] is None


def test_given_inadequate_negatives_when_reference_report_is_saved_then_each_negative_has_diagnostics(corpus, encoder, tmp_path):
    from test_supervised import negatives
    from style_fingerprint import StyleFingerprint
    negatives(tmp_path/'negative_posts', 9)
    bank=tmp_path/'bank'
    fp=StyleFingerprint.build(corpus, bank, holdout_fraction=0)
    assert fp.verifier is None
    assert len(fp.evaluation['negative_diagnostics']) == 9
    assert all(row['decision'] == 'INCONCLUSIVE_OR_MISMATCH' for row in fp.evaluation['negative_diagnostics'])
    assert 'Per-negative-author performance' in (bank/'report.html').read_text()


def test_given_compatible_embeddings_and_changed_verifier_schema_when_rebuilt_then_encoder_cache_is_reused(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    bank=tmp_path/'bank'
    StyleFingerprint.build(corpus, bank, holdout_fraction=0)
    path=bank/'manifest.json'
    manifest=json.loads(path.read_text())
    manifest['feature_schema_version']='previous-verifier-schema'
    path.write_text(json.dumps(manifest))
    encoder.clear()
    rebuilt=StyleFingerprint.build(corpus, bank, holdout_fraction=0)
    assert not encoder
    assert rebuilt.manifest['embedding_cache']['computed'] == 0


def test_given_frozen_character_free_schema_when_building_then_production_excludes_characters(corpus, encoder, tmp_path):
    from test_supervised import negatives
    from style_fingerprint import StyleFingerprint
    negatives(tmp_path/'negative_posts', 12)
    bank = tmp_path/'bank'
    StyleFingerprint.build(corpus, bank, holdout_fraction=0, build_mode='evaluation')
    path = bank/'evaluation_config.json'
    frozen = json.loads(path.read_text())
    frozen['selected_feature_schema'].remove('char_ngram')
    frozen['character_features_enabled'] = False
    frozen['selected_configuration'] = 'hard_negative_weighting_without_character'
    path.write_text(json.dumps(frozen))
    evaluation_bytes = (bank/'evaluation.json').read_bytes()
    production = StyleFingerprint.build(corpus, bank, holdout_fraction=0, build_mode='production')
    assert 'char_ngram' not in production.verifier['feature_names']
    assert production.verifier['estimator'].n_features_in_ == len(frozen['selected_feature_schema'])
    assert production.manifest['evaluation_configuration'] == frozen
    assert (bank/'evaluation.json').read_bytes() == evaluation_bytes
