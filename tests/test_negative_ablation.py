import pytest
from style_fingerprint import evaluation as ev


def test_hard_authors_receive_double_total_mass_with_views_balanced():
    weights = ev.root_sample_weights(['a1','a1','a2','b1','p'], [0,0,0,0,1], ['a','a','a','b',None], hard_negative_authors={'a'})
    assert sum(weights[:3]) == pytest.approx(2 * weights[3])
    assert weights[0] + weights[1] == pytest.approx(weights[2])


def test_ablation_requires_operational_improvement_and_preserved_generalization():
    baseline = dict(tpr_at_5pct_fpr=.8, auroc=.9, true_positive_rate=.9, brier=.1)
    assert ev.choose_configuration({'baseline':baseline,'contrast':{**baseline,'tpr_at_5pct_fpr':.85}}) == 'contrast'
    for change in ({'auroc':.88}, {'true_positive_rate':.86}, {'brier':.12}):
        assert ev.choose_configuration({'baseline':baseline,'hard_negative_weighting':{**baseline,'tpr_at_5pct_fpr':.85,**change}}) == 'baseline'
    assert ev.choose_configuration({'baseline':baseline,'without_character':baseline}) == 'baseline'


def test_grouped_evaluation_compares_five_configs_without_validation_bank_leakage(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    from style_fingerprint.corpus import load_corpus
    negative=tmp_path/'alternative_writers'
    negative.mkdir()
    for i in range(12):
        text=f'---\nauthor_id: writer-{i%3}\nauthor: Writer {i%3}\nsource_type: technical_blog\n---\n' + (f'This invented model {i} explains an experiment with a distinct observation. '*50)
        (negative/f'sample-{i}.md').write_text(text)
    fp=StyleFingerprint.build(corpus,tmp_path/'artifacts',holdout_fraction=0,negative_dir=negative)
    supervised=fp.evaluation['supervised']
    frozen=fp.manifest['evaluation_configuration']
    assert frozen['character_features_enabled'] == ('char_ngram' in fp.verifier['feature_names'])
    production=StyleFingerprint.build(corpus,tmp_path/'artifacts',holdout_fraction=0,negative_dir=negative,build_mode='production')
    assert production.verifier['feature_names'] == frozen['selected_feature_schema']
    assert production.manifest['evaluation_configuration']['character_features_enabled'] == frozen['character_features_enabled']
    assert set(supervised['ablations']) == {'baseline','contrast','hard_negative_weighting','without_character','hard_negative_weighting_without_character'}
    for fold in supervised['folds']:
        assert not set(fold['test_document_ids']) & set(fold['negative_reference_document_ids'])
        assert not set(fold['test_negative_author_ids']) & set(fold['negative_reference_author_ids'])
    assert all(row['split']=='development_oof' and 'hard_negative' in row and 'user_vs_best_negative_gap' in row for row in supervised['held_out_scores'])
    import numpy as np
    for row in supervised['held_out_scores']:
        assert all(np.isfinite(row[name]) for name in ('user_embedding_similarity','best_negative_author_similarity','median_negative_author_similarity','user_vs_best_negative_gap','user_vs_median_negative_gap'))


def test_direct_evaluation_cannot_admit_formal_specification_negatives(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    from style_fingerprint.corpus import Document
    fp=StyleFingerprint.build(corpus,tmp_path/'artifacts',holdout_fraction=0)
    negatives=[Document(f'pep-{i}', 'generic', f'PEP {i} formal specification prose.',f'PEP {i} formal specification prose.',str(i), author=f'writer-{i%3}', metadata={'source_type':'technical_blog','source_url':f'https://peps.python.org/pep-{i:04d}/'}) for i in range(12)]
    ev.run_supervised(fp,negatives)
    assert fp.verifier is None
    assert 'supervised' not in fp.evaluation


def test_weighting_and_character_removal_are_guarded_against_standard_contrast():
    baseline=dict(tpr_at_5pct_fpr=.5,auroc=.8,true_positive_rate=.9,brier=.1)
    contrast={**baseline,'auroc':.95}
    degraded={**baseline,'tpr_at_5pct_fpr':.6,'auroc':.9}
    for candidate in ('hard_negative_weighting','without_character'):
        assert ev.choose_configuration({'baseline':baseline,'contrast':contrast,candidate:degraded}) == 'baseline'


@pytest.mark.parametrize('changes, expected', [({}, False), ({'tpr_at_5pct_fpr': .019}, False), ({'tpr_at_5pct_fpr': .02}, True), ({'auroc': .01}, False), ({'auroc': .011}, True), ({'true_positive_rate': .03}, False), ({'true_positive_rate': .031}, True)])
def test_given_final_pair_when_selecting_then_characters_require_material_value(changes, expected):
    without = dict(tpr_at_5pct_fpr=.8, auroc=.9, true_positive_rate=.9, brier=.1)
    with_char = {key: value + changes.get(key, 0) for key, value in without.items()}
    metrics = {'baseline': {**without, 'tpr_at_5pct_fpr': .5}, 'contrast': {**without, 'tpr_at_5pct_fpr': .6}, 'hard_negative_weighting': with_char, 'hard_negative_weighting_without_character': without}
    selected = ev.choose_configuration(metrics)
    assert selected == ('hard_negative_weighting' if expected else 'hard_negative_weighting_without_character')
