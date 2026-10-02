import json
import numpy as np
import pytest


def test_given_posts_when_built_then_persistent_fingerprint_loads_without_reembedding(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    target = tmp_path / 'artifacts'
    fp = StyleFingerprint.build(corpus, target, holdout_fraction=0)
    assert {'manifest.json','passages.parquet','embeddings.npy','vectorizer.joblib','evaluation.json'} <= {p.name for p in target.iterdir()}
    encoder.clear()
    loaded = StyleFingerprint.load(target)
    assert not encoder
    assert len(loaded.documents) == 6
    assert len(loaded.passages) > 6
    assert loaded.manifest['mode'] == 'reference_similarity'
    assert loaded.manifest['corpus_hashes']
    assert loaded.manifest['model_revision']
    assert loaded.manifest['feature_schema_version']


def test_given_built_model_when_scoring_then_score_evidence_and_components_return(fingerprint, corpus):
    result = fingerprint.score((corpus / 'post-0.markdown').read_text())
    assert 0 <= result.score <= 100
    assert result.word_count >= 500
    assert result.evidence_strength in {'MEDIUM','HIGH'}
    assert {'authorship_embedding','stylometry','char_ngram','ensemble'} <= result.component_scores.keys()
    assert 'probability' not in json.dumps(result.to_dict()).lower()


def test_given_short_prose_when_scored_then_low_evidence_and_warning(fingerprint):
    result = fingerprint.score('I think this is an interesting experiment, and I would like to understand it.')
    assert 0 <= result.score <= 100
    assert result.evidence_strength == 'LOW'
    assert result.diagnostics['warnings']


def test_given_no_usable_candidate_when_scored_then_clear_failure(fingerprint):
    with pytest.raises(ValueError, match='usable|insufficient'):
        fingerprint.score('```\nonly code\n```')


def test_given_unchanged_text_when_rebuilt_then_embeddings_reused(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    target = tmp_path / 'artifacts'
    first = StyleFingerprint.build(corpus, target, holdout_fraction=0)
    encoder.clear()
    second = StyleFingerprint.build(corpus, target, holdout_fraction=0)
    assert encoder == []
    text = (corpus / 'post-0.markdown').read_text()
    assert first.score(text).score == pytest.approx(second.score(text).score, abs=1e-6)


def test_given_changed_passage_or_revision_when_rebuilt_then_stale_cache_is_not_used(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    from style_fingerprint.config import Config
    target = tmp_path / 'artifacts'
    StyleFingerprint.build(corpus, target, holdout_fraction=0)
    encoder.clear()
    path = corpus / 'post-0.markdown'
    path.write_text(path.read_text().replace('interesting', 'surprising'))
    StyleFingerprint.build(corpus, target, holdout_fraction=0)
    assert encoder and all('surprising' in t for t in encoder)
    encoder.clear()
    StyleFingerprint.build(corpus, target, config=Config(model_revision='different-revision'), holdout_fraction=0)
    assert len(encoder) >= 6


def test_given_two_builds_when_same_seed_then_deterministic(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    a = StyleFingerprint.build(corpus, tmp_path / 'a', holdout_fraction=0)
    b = StyleFingerprint.build(corpus, tmp_path / 'b', holdout_fraction=0)
    text = (corpus / 'post-1.markdown').read_text()
    assert a.score(text).to_dict() == b.score(text).to_dict()


def test_given_held_out_post_when_evaluated_then_no_reference_or_statistics_leakage(fingerprint):
    evaluation = fingerprint.evaluate()
    assert len(evaluation['folds']) == 6
    for fold in evaluation['folds']:
        assert fold['candidate_document_id'] not in fold['reference_document_ids']
        assert fold['candidate_document_id'] not in fold['statistics_document_ids']
        assert len(fold['reference_document_ids']) == 5
        assert fold['duplicate_passages_removed'] >= 0
    assert {'authorship_embedding','stylometry','char_ngram','embedding_stylometry','ensemble'} <= evaluation['ablations'].keys()
    assert np.isfinite(evaluation['score_variance'])


def test_given_incompatible_manifest_when_loaded_then_error(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    target = tmp_path / 'artifacts'
    StyleFingerprint.build(corpus, target, holdout_fraction=0)
    path = target / 'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['feature_schema_version'] = 'future'
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='incompatible|schema'):
        StyleFingerprint.load(target)
