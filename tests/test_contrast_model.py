"""BDD contracts for negative references, persisted diagnostics, and stale policy."""
import json
import numpy as np
import pytest


def test_given_negative_author_in_validation_when_compared_then_entire_author_is_excluded(fingerprint):
    from style_fingerprint.corpus import Document, Passage
    # Given two roots by one negative writer and a different negative writer.
    for root, author, vector in [('negative/a', 'a', [1., 0.]), ('negative/b', 'a', [1., 0.]), ('negative/c', 'c', [0., 1.])]:
        fingerprint.documents.append(Document(root, root, 'invented human prose', 'invented human prose', 'hash', metadata={}, root_document_id=root, author_id=author))
        fingerprint.passages.append(Passage(root, 0, 'invented human prose', 0, 20, 3, root_document_id=root, author_id=author))
    fingerprint.embeddings = np.vstack([np.tile([.5, .5], (len(fingerprint.passages)-3, 1)), [1., 0.], [1., 0.], [0., 1.]])
    # When the author is held out, only the independent author's reference remains.
    result = fingerprint._negative_contrast(np.array([[1., 0.]]), ['negative/a', 'negative/b', 'negative/c'], .8, excluded_root='negative/a', excluded_author='a')
    # Then the tempting exact matches cannot inflate negative similarity.
    assert result['best_negative_author_similarity'] == 0
    assert result['user_vs_best_negative_gap'] == .8


def test_given_equal_user_similarity_when_alternative_writer_is_close_then_gap_is_smaller(fingerprint):
    from style_fingerprint.corpus import Document, Passage
    fingerprint.documents.append(Document('negative/a', 'invented', 'invented prose here', 'invented prose here', 'hash', metadata={}, root_document_id='negative/a', author_id='other'))
    fingerprint.passages.append(Passage('negative/a', 0, 'invented prose here', 0, 19, 3, root_document_id='negative/a', author_id='other'))
    fingerprint.embeddings = np.vstack([np.tile([1., 0.], (len(fingerprint.passages)-1, 1)), [1., 0.]])
    close = fingerprint._negative_contrast(np.array([[1., 0.]]), ['negative/a'], .8)
    distant = fingerprint._negative_contrast(np.array([[0., 1.]]), ['negative/a'], .8)
    assert close['user_vs_best_negative_gap'] < distant['user_vs_best_negative_gap']
    assert close['user_embedding_similarity'] == distant['user_embedding_similarity']


def test_given_old_corpus_policy_when_loading_then_fingerprint_requires_rebuild(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    bank = tmp_path/'bank'
    StyleFingerprint.build(corpus, bank, holdout_fraction=0)
    path = bank/'manifest.json'
    manifest = json.loads(path.read_text())
    manifest['negative_corpus_policy'] = 'legacy-peps'
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='policy|rebuild|incompatible'):
        StyleFingerprint.load(bank)


def test_given_evaluation_when_saved_then_all_diagnostic_columns_and_explicit_splits_exist(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    import pandas as pd
    bank = tmp_path/'bank'
    StyleFingerprint.build(corpus, bank, holdout_fraction=0)
    rows = pd.read_parquet(bank/'evaluation_predictions.parquet')
    assert {'best_negative_author_similarity', 'median_negative_author_similarity', 'user_vs_best_negative_gap', 'hard_negative', 'source_type'} <= set(rows)
    assert set(rows['split']) == {'development_oof'}
    assert not rows['hard_negative'].any()


def test_given_legacy_negative_in_memory_when_bank_is_compared_then_formal_prose_is_excluded(fingerprint):
    from style_fingerprint.corpus import Document, Passage
    root='negative/legacy'
    fingerprint.documents.append(Document(root, 'invented.md', 'PEP: 123\nFormal proposal prose here.', 'Formal proposal prose here.', 'hash', metadata={'source_type':'technical_blog'}, root_document_id=root, author_id='other'))
    fingerprint.passages.append(Passage(root, 0, 'Formal proposal prose here.', 0, 27, 5, root_document_id=root, author_id='other'))
    fingerprint.embeddings = np.vstack([np.tile([1., 0.], (len(fingerprint.passages)-1, 1)), [1., 0.]])
    result=fingerprint._negative_contrast(np.array([[1.,0.]]), [root], .8)
    assert result['best_negative_author_similarity'] == 0


def test_given_negative_email_when_evaluated_then_only_clean_authored_body_is_scored(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    from style_fingerprint.corpus import word_count
    root=tmp_path/'negative_posts'/'email'/'other-writer'
    root.mkdir(parents=True)
    body='I reviewed the model carefully and compared several useful observations before sharing these findings.'
    (root/'message.md').write_text('---\nsource_type: email\nauthor: Other Writer\n---\n'+body+'\n\nBest regards,\nOther Writer\n\n> '+('Quoted earlier content should be excluded. '*25))
    fp=StyleFingerprint.build(corpus,tmp_path/'bank',holdout_fraction=0)
    doc=next(d for d in fp.documents if d.source_type=='email')
    row=next(r for r in fp._prediction_rows() if r['root_document_id']==doc.root_document_id)
    assert row['word_count']==word_count(doc.clean_text)
    assert fp._document_features[doc.document_id]['quote_paragraph_rate'] == 0


def test_given_changed_negative_inputs_when_production_refits_then_frozen_evaluation_is_stale(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    root=tmp_path/'negative_posts';root.mkdir()
    file=root/'sample.md';file.write_text('An invented technical model explains the observations clearly.')
    bank=tmp_path/'bank'
    StyleFingerprint.build(corpus,bank,holdout_fraction=0)
    file.write_text('Another invented technical model explains entirely different observations clearly.')
    with pytest.raises(ValueError,match='negative.*evaluation|evaluation.*negative'):
        StyleFingerprint.build(corpus,bank,holdout_fraction=0,build_mode='production')


def test_given_duplicate_source_roots_when_predictions_are_saved_then_each_root_keeps_a_row(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    from test_supervised import negatives
    import pandas as pd
    (corpus/'copy.md').write_bytes((corpus/'post-0.markdown').read_bytes())
    negatives(tmp_path/'negative_posts',12)
    bank=tmp_path/'bank'
    fp=StyleFingerprint.build(corpus,bank,holdout_fraction=0)
    rows=pd.read_parquet(bank/'evaluation_predictions.parquet')
    assert rows['root_document_id'].is_unique
    assert set(rows['root_document_id']) == {d.root_document_id for d in fp.documents}
    original=rows.loc[rows['root_document_id']=='post-0.markdown','compatibility_score'].iloc[0]
    duplicate=rows.loc[rows['root_document_id']=='copy.md','compatibility_score'].iloc[0]
    assert original == duplicate
