"""Primary positive tests are sealed off from fitting and model selection."""
from pathlib import Path
import json
import numpy as np
import pytest


def reserved(tmp_path, count=3):
    root = tmp_path / 'test_corpus' / 'blog_posts'
    root.mkdir(parents=True)
    for i in range(count):
        prose = (f'I reviewed reserved scenario {i} and would like to share the practical observations. '
                 'Perhaps we should discuss the interesting details together tomorrow, because there is much to consider. ')*6
        (root / f'reserved-{i}.md').write_text('---\ntitle: Reserved example\n---\n'+prose)
    return root


def test_given_primary_blog_tests_when_built_then_they_are_not_part_of_the_training_bank(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    reserved(tmp_path)
    fp = StyleFingerprint.build(corpus, tmp_path / 'out', holdout_fraction=0)
    assert len(fp.manifest['historical_document_ids']) == 6
    ids = fp.manifest['primary_positive_test_ids']
    assert len(ids) == 3 and all(i.startswith('primary_test/') for i in ids)
    assert not set(ids) & {d.document_id for d in fp.documents}
    assert not set(ids) & {p.document_id for p in fp.passages}
    assert not set(ids) & set(fp.manifest['document_features'])
    assert fp.manifest['dataset_counts']['primary_positive_test_documents'] == 3
    assert fp.manifest['dataset_counts']['total_positive_documents'] == 9
    assert len(fp.manifest['primary_positive_test_documents']) == 3
    loaded = StyleFingerprint.load(tmp_path / 'out')
    assert loaded.evaluation['primary_positive_tests'] == fp.evaluation['primary_positive_tests']


def test_given_primary_tests_and_negatives_when_selected_then_only_development_rows_determine_the_model(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    from test_supervised import negatives
    reserved(tmp_path)
    negatives(tmp_path / 'negative_posts', 12)
    fp = StyleFingerprint.build(corpus, tmp_path / 'out', holdout_fraction=0)
    heldout = set(fp.manifest['primary_positive_test_ids'])
    supervised = fp.evaluation['supervised']
    assert not heldout & {r['document_id'] for r in supervised['held_out_scores']}
    for fold in fp.evaluation['folds']:
        for field in ['candidate_document_id','reference_document_ids','statistics_document_ids','normalization_document_ids']:
            values = [fold[field]] if isinstance(fold[field],str) else fold[field]
            assert not heldout & set(values)
    for fold in supervised['folds']:
        for field in ['training_document_ids','test_document_ids','reference_document_ids','calibration_training_ids']:
            assert not heldout & set(fold[field])
        for inner in fold['inner_folds']:
            for field in ['training_document_ids','test_document_ids','reference_document_ids']:
                assert not heldout & set(inner[field])
    primary = fp.evaluation['primary_positive_tests']
    assert primary['count'] == 3
    assert primary['positive_only'] is True
    assert primary['selected_model'] == supervised['selected_model']
    assert 'auroc' not in primary and 'false_positive_rate' not in primary
    assert primary['accepted_at_match_threshold'] == sum(row['decision'] == 'MATCH' for row in primary['documents'])
    assert primary['acceptance_rate_at_match_threshold'] == pytest.approx(primary['accepted_at_match_threshold']/3)
    assert all(0 <= r['score'] <= 100 and r['evidence_strength'] for r in primary['documents'])
    before = fp.verifier['calibrator'].coef_.copy()
    import joblib
    model_hash = joblib.hash(fp.verifier)
    vocabulary = fp._reference(fp.manifest['historical_document_ids'])['vectorizer'].vocabulary_.copy()
    repeated = fp._evaluate_primary_positive_tests()
    assert repeated == primary
    np.testing.assert_array_equal(before,fp.verifier['calibrator'].coef_)
    assert joblib.hash(fp.verifier) == model_hash
    assert vocabulary == fp._reference(fp.manifest['historical_document_ids'])['vectorizer'].vocabulary_


@pytest.mark.parametrize('partial', [False, True])
def test_given_copied_primary_test_prose_when_building_then_contamination_is_rejected_before_inference(corpus, encoder, tmp_path, partial):
    from style_fingerprint import StyleFingerprint
    root = reserved(tmp_path,1)
    raw = (root/'reserved-0.md').read_text()
    body = raw.split('---\n')[-1]
    if partial:
        body += '\n\nThis is an additional independent paragraph.'
    (corpus/'copied.md').write_text(body)
    with pytest.raises(ValueError,match='[Pp]rimary.*overlap|contaminat'):
        StyleFingerprint.build(corpus,tmp_path/'out', holdout_fraction=0)
    assert not encoder


def test_given_explicit_missing_primary_test_path_when_building_then_it_is_not_silently_ignored(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    with pytest.raises(ValueError,match='Markdown|test'):
        StyleFingerprint.build(corpus,tmp_path/'out',primary_test_dir=tmp_path/'missing', holdout_fraction=0)


def test_given_primary_tests_when_cli_evaluated_then_the_primary_report_is_displayed_first(corpus, encoder, tmp_path, capsys):
    from style_fingerprint.cli import main
    root = reserved(tmp_path)
    assert main(['build', '--no-holdout','--corpus',str(corpus),'--primary-positive-tests',str(root),'--artifacts',str(tmp_path/'out')]) == 0
    output=capsys.readouterr().out
    assert '3 primary positive test' in output
    assert main(['evaluate','--artifacts',str(tmp_path/'out')]) == 0
    output=capsys.readouterr().out
    assert output.index('Primary positive test') < output.index('Document-grouped')
    assert main(['evaluate','--artifacts',str(tmp_path/'out'),'--json']) == 0
    assert json.loads(capsys.readouterr().out)['primary_positive_tests']['count'] == 3
