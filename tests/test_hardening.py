import json
import pytest


def test_given_compact_scoring_when_prose_scored_then_analogues_return_without_deletions(fingerprint):
    result = fingerprint.score(fingerprint.documents[0].clean_text, explain=False)
    assert result.nearest_reference_passages
    assert result.diagnostics['sentence_deletions_evaluated'] == 0


def test_given_saved_fingerprint_when_loaded_then_persisted_features_are_reused(corpus, encoder, tmp_path, monkeypatch):
    from style_fingerprint import StyleFingerprint
    import style_fingerprint.model as module
    target = tmp_path / 'artifacts'
    StyleFingerprint.build(corpus, target, holdout_fraction=0)
    def should_not_reprocess(*args, **kwargs):
        raise AssertionError('Unchanged historical features must not be reprocessed on load')
    monkeypatch.setattr(module, 'extract_features', should_not_reprocess)
    fp = StyleFingerprint.load(target)
    assert len(fp.documents) == 6


def test_given_markdown_navigation_when_cleaned_then_generated_links_are_removed():
    from style_fingerprint.corpus import clean_markdown
    text = '# Table of contents\n\n- [First section](#first)\n- [Second section](#second)\n\nAuthor prose stays here.\n\n[Previous post](/previous/) | [Next post](/next/)'
    clean = clean_markdown(text)
    assert 'First section' not in clean and 'Second section' not in clean
    assert 'Previous post' not in clean and 'Next post' not in clean
    assert 'Table of contents' not in clean
    assert 'Author prose stays here.' in clean


def test_given_supervised_artifacts_when_loaded_then_scores_and_contributions_roundtrip(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    from test_supervised import negatives
    negatives(tmp_path / 'negative_posts', 10)
    target = tmp_path / 'artifacts'
    fp = StyleFingerprint.build(corpus, target, holdout_fraction=0)
    loaded = StyleFingerprint.load(target)
    text = fp.documents[0].clean_text
    before, after = fp.score(text, explain=False), loaded.score(text, explain=False)
    assert after.score == pytest.approx(before.score, abs=1e-6)
    assert after.component_scores == pytest.approx(before.component_scores, abs=1e-6)
    assert after.evidence_strength == before.evidence_strength
    assert after.diagnostics['contributions'] == before.diagnostics['contributions']
    rerun = loaded.evaluate()
    assert rerun['supervised']['metrics'] == fp.evaluation['supervised']['metrics']


def test_given_duplicate_negative_files_when_built_then_duplicates_do_not_enable_supervision(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    root = tmp_path / 'negative_posts'
    root.mkdir()
    for i in range(10):
        (root / f'copy-{i}.md').write_text('This is one repeated negative document. ' * 60)
    fp = StyleFingerprint.build(corpus, tmp_path / 'artifacts', holdout_fraction=0)
    assert fp.manifest['mode'] == 'reference_similarity'


def test_given_duplicate_passages_when_evaluated_then_held_out_text_is_absent(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    repeated = '\n\n' + ('This exact shared passage must not appear across validation folds. ' * 30)
    for path in corpus.glob('*.markdown'):
        path.write_text(path.read_text() + repeated)
    fp = StyleFingerprint.build(corpus, tmp_path / 'artifacts', holdout_fraction=0)
    docs = {d.document_id: d for d in fp.documents}
    for fold in fp.evaluation['folds']:
        candidate = [p.text for p in fp.passages if p.document_id == fold['candidate_document_id']]
        reference = fp._reference(fold['reference_document_ids'], candidate)
        assert not set(candidate) & {fp.passages[i].text for i in reference['indices']}
        assert fold['duplicate_passages_removed'] > 0


def test_given_corrupt_artifact_when_loaded_then_clear_failure(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    target = tmp_path / 'artifacts'
    StyleFingerprint.build(corpus, target, holdout_fraction=0)
    (target / 'vectorizer.joblib').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='corrupt|incompatible'):
        StyleFingerprint.load(target)


def test_given_author_links_and_headings_when_cleaned_then_their_prose_is_preserved():
    from style_fingerprint.corpus import clean_markdown
    text = '## Contents\n\nI explain the contents here. Read [the next post](/next/) for the continuation.\n\nI discuss [Next post](/next/) in this sentence.'
    clean = clean_markdown(text)
    assert 'Contents' in clean
    assert 'I discuss Next post in this sentence.' in clean


def test_given_tiny_unmergeable_tail_when_long_candidate_explained_then_result_survives(fingerprint):
    text = 'I think this is useful. ' * 140 + '\n\nHi there.'
    result = fingerprint.score(text)
    assert result.word_count == 702
    assert 0 <= result.score <= 100
    tiny = next(p for p in result.anomalous_passages if 'Hi there' in p['text'])
    assert tiny['insufficient_prose'] and tiny['score'] is None
