import pytest


def negatives(root, count, authors=True):
    root.mkdir()
    for i in range(count):
        author = f'author: Other {i % 3}\n' if authors else ''
        (root / f'negative-{i}.md').write_text('---\n' + author + '---\n' + (f'BUY offer {i}! WIN! Act now! This incredible product delivers everything immediately! ' * 45))


@pytest.mark.parametrize('count,authors,expected', [(9,True,'reference_similarity'),(10,True,'supervised'),(10,False,'supervised')])
def test_given_negative_documents_when_built_then_threshold_controls_mode(corpus, encoder, tmp_path, count, authors, expected):
    from style_fingerprint import StyleFingerprint
    negative = tmp_path / 'negative_posts'
    negatives(negative, count, authors)
    fp = StyleFingerprint.build(corpus, tmp_path / 'artifacts', holdout_fraction=0)
    assert fp.manifest['mode'] == expected
    if expected == 'supervised':
        assert fp.evaluation['supervised']['calibration_enabled']
        assert 'logistic_regression' in fp.evaluation['supervised']['models']
        assert fp.evaluation['supervised']['selected_model'] in {'logistic_regression','lightgbm'}
        assert (tmp_path / 'artifacts' / 'verifier.joblib').exists()
        assert {'auroc','average_precision','eer','tpr_at_1pct_fpr','tpr_at_5pct_fpr','brier','calibration_error'} <= fp.evaluation['supervised']['metrics'].keys()
        for fold in fp.evaluation['supervised']['folds']:
            assert not set(fold['test_document_ids']) & set(fold['training_document_ids'])
            assert not set(fold['test_positive_ids']) & set(fold['reference_document_ids'])
            assert not set(fold['test_document_ids']) & set(fold['calibration_training_ids'])
        result = fp.score(fp.documents[0].clean_text)
        assert 0 <= result.score <= 100
        assert result.diagnostics['contributions']


def test_given_one_known_negative_author_when_built_then_supervision_is_disabled(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    root = tmp_path / 'negative_posts'
    negatives(root, 10)
    for p in root.glob('*.md'):
        p.write_text(p.read_text().replace('Other 1','Other 0').replace('Other 2','Other 0'))
    fp = StyleFingerprint.build(corpus, tmp_path / 'artifacts', holdout_fraction=0)
    assert fp.manifest['mode'] == 'reference_similarity'
    assert fp.verifier is None


def test_given_ensemble_metrics_when_selecting_then_boosting_requires_real_margin():
    from style_fingerprint.model import choose_verifier
    assert choose_verifier(.85, .869) == 'logistic_regression'
    assert choose_verifier(.85, .871) == 'lightgbm'
