"""Email integration scenarios; fixtures contain invented, non-private prose."""
from pathlib import Path
import pytest


def test_given_plain_email_when_ingested_then_authored_prose_and_provenance_survive(tmp_path):
    from style_fingerprint.corpus import load_work_corpus
    raw = ('Subject: Planning\nFrom: author@example.test\nTo: colleague@example.test\n\n'
           'Hi Sam,\n\n    I think this is useful! Version_2 should work.\n'
           '·         We can check the data together.\nImage\n\n'
           'Michael Becker\nExample Researcher\nEmail: author@example.test\nExample Organization\n'
           'On Tuesday, Sam wrote:\n> Someone else wrote this.\n')
    (tmp_path / 'synthetic-message.txt').write_text(raw)
    (tmp_path / 'ignore.json').write_text('{}')
    docs = load_work_corpus(tmp_path)
    assert len(docs) == 1
    doc = docs[0]
    assert doc.document_id == 'work/synthetic-message.txt'
    assert doc.raw_markdown == raw
    assert doc.metadata['genre'] == 'work_email'
    assert doc.metadata['author_id'] == 'mdbecker'
    assert doc.author == 'Michael Becker'
    assert doc.source_file == str((tmp_path / 'synthetic-message.txt').resolve())
    assert 'I think this is useful! Version_2 should work.' in doc.clean_text
    assert 'We can check the data together.' in doc.clean_text
    for excluded in ['Subject:', 'example.test', 'Someone else', 'Image', 'Example Researcher', 'Example Organization', 'Michael Becker']:
        assert excluded not in doc.clean_text


def test_given_email_without_boilerplate_when_cleaned_then_greetings_and_punctuation_remain():
    from style_fingerprint.corpus import clean_email
    text = 'Hello Alex,\n\n    I agree (mostly), but why?\n\nThanks for your time!'
    assert clean_email(text) == 'Hello Alex,\n\nI agree (mostly), but why?\n\nThanks for your time!'


def test_given_empty_explicit_work_corpus_when_loaded_then_clear_error(tmp_path):
    from style_fingerprint.corpus import load_work_corpus
    with pytest.raises(ValueError, match='email|text|prose'):
        load_work_corpus(tmp_path)


def test_given_sibling_work_emails_when_built_then_positives_are_namespaced_and_cached(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    work = tmp_path / 'work_corpus'
    work.mkdir()
    (work / 'post-0.txt').write_text('Hello Casey,\n\nI checked the new comparison and would like to discuss the practical implications tomorrow. Thanks!')
    artifacts = tmp_path / 'artifacts'
    fp = StyleFingerprint.build(corpus, artifacts, holdout_fraction=0)
    ids = fp.manifest['historical_document_ids']
    assert len(ids) == 7 and 'work/post-0.txt' in ids and 'post-0.markdown' in ids
    assert fp.manifest['positive_corpus_counts'] == {'blog': 6, 'work_email': 1}
    email = next(d for d in fp.documents if d.document_id.startswith('work/'))
    assert email.metadata['genre'] == 'work_email'
    assert any('Mixed positive genres' in w for w in fp.manifest['warnings'])
    assert any('short work emails' in w.lower() for w in fp.manifest['warnings'])
    assert any(p.document_id == email.document_id for p in fp.passages)
    loaded = StyleFingerprint.load(artifacts)
    assert loaded.manifest['historical_document_ids'] == ids
    assert loaded.documents[-1].clean_text == email.clean_text
    result = loaded.score(email.clean_text, explain=False)
    assert 0 <= result.score <= 100
    calls = len(encoder)
    rebuilt = StyleFingerprint.build(corpus, artifacts, holdout_fraction=0)
    assert len(encoder) == calls
    assert rebuilt.manifest['embedding_cache']['computed'] == 0
    blog_only = StyleFingerprint.build(corpus, tmp_path / 'blog-only', work_dir=False, holdout_fraction=0)
    assert len(blog_only.manifest['historical_document_ids']) == 6


def test_given_explicit_missing_work_root_when_built_then_it_is_not_silently_ignored(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    with pytest.raises(ValueError, match='email|text|prose'):
        StyleFingerprint.build(corpus, tmp_path / 'out', work_dir=tmp_path / 'missing', holdout_fraction=0)


def test_given_explicit_work_root_when_cli_built_then_positive_emails_are_included(corpus, encoder, tmp_path, capsys):
    from style_fingerprint.cli import main
    work = tmp_path / 'emails'
    work.mkdir()
    (work / 'synthetic-message.TXT').write_text('Hi Casey,\n\nThis is a clear plan, and I think we should compare the numbers together.')
    assert main(['build', '--no-holdout', '--corpus', str(corpus), '--work-corpus', str(work), '--artifacts', str(tmp_path / 'out')]) == 0
    assert '7 historical documents' in capsys.readouterr().out
    assert main(['build', '--no-holdout', '--corpus', str(corpus), '--no-work-corpus', '--artifacts', str(tmp_path / 'only')]) == 0
    assert '6 historical documents' in capsys.readouterr().out


def test_given_mixed_positive_genres_when_evaluated_then_each_genre_and_heldout_source_is_reported(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    work = tmp_path / 'work_corpus'
    work.mkdir()
    for i in range(3):
        (work / f'{i}.txt').write_text(f'Hi Casey,\n\nI reviewed scenario {i} today and think the result is helpful. Can we discuss the next steps tomorrow?')
    fp = StyleFingerprint.build(corpus, tmp_path / 'out', holdout_fraction=0)
    report = fp.evaluate()
    assert set(report['positive_genres']) == {'blog', 'work_email'}
    assert report['positive_genres']['work_email']['documents'] == 3
    assert report['positive_genres']['blog']['documents'] == 6
    folds = report['folds']
    emails = [f for f in folds if f['genre'] == 'work_email']
    assert len(emails) == 3
    assert all(f['source_file'].endswith('.txt') and f['usable_words'] > 0 for f in emails)
    assert all(f['candidate_document_id'] not in f['reference_document_ids'] for f in folds)
    assert all(f['candidate_document_id'] not in f['statistics_document_ids'] for f in folds)
    assert all(f['candidate_document_id'] not in f['normalization_document_ids'] for f in folds)
    assert 0 <= report['positive_genres']['work_email']['mean_compatibility'] <= 100


def test_given_email_image_placeholder_when_features_built_then_boilerplate_does_not_change_features(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    from style_fingerprint.features import extract_features
    work = tmp_path / 'work_corpus'
    work.mkdir()
    (work / 'one.txt').write_text('Hello Casey,\n\nI think this is useful, and we should check the comparison.\n\n> # Quoted heading\n> - Quoted list item\n\nImage\n\nMichael Becker\nExample Researcher\nEmail: person@example.test')
    fp = StyleFingerprint.build(corpus, tmp_path / 'out', holdout_fraction=0)
    email = next(d for d in fp.documents if d.document_id.startswith('work/'))
    assert fp.manifest['document_features'][email.document_id] == extract_features(email.clean_text, email.clean_text)


def test_given_many_reference_combinations_when_evaluated_then_tfidf_cache_is_bounded(fingerprint):
    ids = fingerprint.manifest['historical_document_ids']
    first = fingerprint._reference(ids)['char_matrix'].toarray()
    for i in range(70):
        fingerprint._reference(ids, excluded_texts=[f'Absent unique marker {i}'])
    assert len(fingerprint._reference_cache) <= 32
    import numpy as np
    np.testing.assert_allclose(fingerprint._reference(ids)['char_matrix'].toarray(), first)


def test_given_work_positives_and_real_negative_authors_when_trained_then_genre_metrics_and_fold_exclusion_survive(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    work = tmp_path / 'work_corpus'
    work.mkdir()
    for i in range(3):
        (work / f'{i}.txt').write_text(f'Hello Morgan, I checked review {i} this morning. I think we can discuss the findings tomorrow, but we should compare the outcomes first!')
    negative = tmp_path / 'negative_posts'
    negative.mkdir()
    for i in range(12):
        (negative / f'{i}.md').write_text(f'---\nauthor: Other {i % 3}\nauthor_id: other-{i % 3}\n---\nTechnical procedure {i} demonstrates that numerical experiments require careful measurement. The resulting approximation varies across input distributions.')
    fp = StyleFingerprint.build(corpus, tmp_path / 'out', holdout_fraction=0)
    supervised = fp.evaluation['supervised']
    assert supervised['positive_genre_weighting'] == 'equal root document weight across positive sources'
    genres = supervised['per_positive_genre']
    assert genres['blog']['documents'] == 6
    assert genres['work_email']['documents'] == 3
    assert 0 <= genres['work_email']['accept_rate_at_match_threshold'] <= 1
    heldout = supervised['held_out_scores']
    assert sum(row.get('genre') == 'work_email' and row['label'] == 1 for row in heldout) == 3
    for fold in supervised['folds']:
        assert not set(fold['test_positive_ids']) & set(fold['reference_document_ids'])
        assert not set(fold['test_document_ids']) & set(fold['calibration_training_ids'])
        for inner in fold['inner_folds']:
            assert not set(inner['test_document_ids']) & set(inner['reference_document_ids'])
    loaded = StyleFingerprint.load(tmp_path / 'out')
    assert loaded.evaluation['supervised']['per_positive_genre'] == genres


def test_given_private_work_corpus_when_repository_shared_then_ignore_rules_exclude_raw_emails():
    assert '/work_corpus/' in Path('.gitignore').read_text().splitlines()


def test_given_email_candidate_when_scored_then_training_and_candidate_cleaning_match(fingerprint):
    from style_fingerprint.corpus import clean_email, word_count
    raw = 'Subject: Follow up\n\nHello Casey,\n\nI checked Version_2 today, and I think we should compare the outcomes!\n\nImage\n\nMichael Becker\nExample Researcher\nEmail: author@example.test'
    cleaned = clean_email(raw)
    result = fingerprint.score(raw, input_format='email')
    direct = fingerprint.score(cleaned, input_format='email')
    assert result.word_count == word_count(cleaned)
    assert result.to_dict() == direct.to_dict()
    assert result.diagnostics['input_format'] == 'email'
    assert all('Image' not in row['text'] and 'Example Researcher' not in row['text'] for row in result.anomalous_passages)
    with pytest.raises(ValueError, match='format'):
        fingerprint.score(raw, input_format='unsupported')


def test_given_email_input_flag_when_cli_scored_then_signature_is_not_measured(fingerprint, tmp_path, capsys):
    from style_fingerprint.cli import main
    raw = 'Subject: Next steps\n\nHi Casey, I think this comparison is helpful.\n\n-- \nAutomatic signature'
    file = tmp_path / 'candidate.txt'
    file.write_text(raw)
    artifacts = tmp_path / 'artifacts'
    assert main(['score', str(file), '--input-format', 'email', '--artifacts', str(artifacts), '--json']) == 0
    report = __import__('json').loads(capsys.readouterr().out)
    assert report['word_count'] == 8
    assert report['diagnostics']['input_format'] == 'email'


def test_given_email_with_long_plaintext_when_explained_then_subscores_use_email_format(fingerprint, monkeypatch):
    calls = []
    original = fingerprint.score
    def score(text, **kwargs):
        calls.append(kwargs.get('input_format', 'markdown'))
        return original(text, **kwargs)
    monkeypatch.setattr(fingerprint, 'score', score)
    text = ('I think Version_2 will help us compare the results, and we should review the evidence together! ' * 12)
    result = fingerprint.score(text, input_format='email')
    assert result.diagnostics['sentence_deletions_evaluated'] > 0
    assert calls and set(calls) == {'email'}


def test_given_positive_sources_when_calibrated_then_source_labels_do_not_change_the_score_scale():
    import numpy as np
    from style_fingerprint.model import fit_calibrator
    margins = [-2., -1., .2, .7, 2., 3., 4.]
    labels = [0, 0, 1, 1, 1, 1, 1]
    baseline = fit_calibrator(margins, labels, 42)
    mixed = fit_calibrator(margins, labels, 42, positive_genres=['other','other','blog','blog','work_email','work_email','gmail_email'])
    np.testing.assert_allclose(baseline.predict_proba(np.array([[.5]])), mixed.predict_proba(np.array([[.5]])), atol=1e-6)


def test_given_positive_source_labels_when_verifier_trained_then_labels_are_provenance_only():
    import numpy as np
    from style_fingerprint.corpus import Document
    from style_fingerprint.model import _fit_comparison_estimator
    docs = [Document(str(i), '', '', '', '', metadata={'genre': 'blog' if i < 2 else 'work_email'}) for i in range(10)]
    positive_ids = {str(i) for i in range(8)}
    x = np.array([[i, i*i % 7] for i in range(10)],dtype=float)
    mixed = _fit_comparison_estimator('logistic_regression',42,x,docs,positive_ids)
    for d in docs:
        d.metadata['genre'] = 'blog'
    single = _fit_comparison_estimator('logistic_regression',42,x,docs,positive_ids)
    np.testing.assert_allclose(mixed.decision_function(x),single.decision_function(x),atol=1e-6)
