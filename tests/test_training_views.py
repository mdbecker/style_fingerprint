"""Given historical prose, views preserve independent source identities."""
from style_fingerprint.corpus import Document, generate_training_views, chunk_text
from style_fingerprint.holdout import document_groups


def document(words=1200, author=None):
    paragraphs = [' '.join([f'paragraph{i}'] * 100) + '.' for i in range(words // 100)]
    text = '\n\n'.join(paragraphs)
    return Document('original', 'generic', text, text, 'hash', metadata={'genre': 'negative', 'author_id': author} if author else {})


def test_long_document_has_bounded_contiguous_deterministic_views():
    original = document()
    views = generate_training_views(original, seed=7)
    assert 2 < len(views) <= 6
    assert views == generate_training_views(original, seed=7)
    assert all(v.root_document_id == original.document_id for v in views)
    assert all(v.clean_text in original.clean_text for v in views)
    assert all(300 <= v.word_count <= 700 for v in views[:-1])
    assert views[-1].clean_text == original.clean_text
    assert all(v.clean_text.startswith('paragraph') and v.clean_text.endswith('.') for v in views)


def test_short_document_remains_one_view():
    original = document(200)
    views = generate_training_views(original)
    assert len(views) == 1
    assert views[0].clean_text == original.clean_text


def test_medium_document_has_two_windows_and_full_view():
    assert len(generate_training_views(document(800))) == 3


def test_views_and_passages_keep_author_and_root_identity():
    original = document(author='known-author')
    views = generate_training_views(original)
    assert all(v.author_id == 'known-author' for v in views)
    passages = chunk_text(views[0].clean_text, views[0].document_id,
                          root_document_id=views[0].root_document_id, author_id=views[0].author_id)
    assert all(p.root_document_id == 'original' and p.author_id == 'known-author' for p in passages)


def test_same_root_and_known_negative_author_cannot_cross_groups():
    original = document(author='known-author')
    other = document(author='known-author')
    other.document_id = 'other'
    other.root_document_id = 'other'
    other.clean_text = other.clean_text.replace('paragraph', 'different')
    views = generate_training_views(original) + generate_training_views(other)
    groups = document_groups(views)
    assert len(set(groups.values())) == 1


def test_oversized_paragraph_uses_whole_sentences():
    text = ' '.join(' '.join([f'sentence{i}'] * 100) + '.' for i in range(12))
    original = Document('root', 'generic', text, text, 'hash')
    views = generate_training_views(original)
    assert len(views) > 1
    assert all(v.clean_text.endswith('.') for v in views)
    assert all(v.word_count <= 700 for v in views[:-1])


def test_oversized_indivisible_sentence_is_never_fragmented():
    text = ' '.join(['unbroken'] * 1200) + '.'
    original = Document('root', 'generic', text, text, 'hash')
    assert len(generate_training_views(original)) == 1


def test_single_medium_paragraph_never_duplicates_full_document():
    # Given a single indivisible paragraph within the window cap.
    text = ' '.join(['paragraph'] * 650) + '.'
    original = Document('root', 'generic', text, text, 'hash')
    # When aligned training observations are prepared.
    views = generate_training_views(original)
    # Then no duplicate window increases that paragraph's influence.
    assert len(views) == 1
    assert len({view.clean_text for view in views}) == len(views)
