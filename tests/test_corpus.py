from pathlib import Path
import pytest


def test_given_nested_markdown_when_discovered_then_all_extensions_and_metadata_survive(tmp_path):
    from style_fingerprint.corpus import load_corpus
    nested = tmp_path / 'nested'
    nested.mkdir()
    fixture = Path('tests/fixtures/prose.md').read_text()
    for name in ['one.md', 'two.markdown', 'three.MD']:
        (nested / name).write_text(fixture)
    (nested / 'ignore.txt').write_text('not a post')
    docs = load_corpus(tmp_path)
    assert len(docs) == 3
    assert all(d.document_id.startswith('nested/') for d in docs)
    assert all(d.raw_markdown == fixture and d.author == 'Fixture Author' for d in docs)


def test_given_markup_when_cleaned_then_only_prose_remains():
    from style_fingerprint.corpus import clean_markdown
    text = clean_markdown(Path('tests/fixtures/prose.md').read_text())
    for excluded in ['private title', 'SECRET_CODE', 'OCTOPRESS_SECRET', 'INLINE_SECRET', 'https://', 'GENERATED_TOC', '{%', '<em>', '**', '![']:
        assert excluded not in text
    for kept in ['A useful heading', 'ordinary prose', 'the link', 'This list item stays.', 'Quoted prose stays', '(including this aside)']:
        assert kept in text


def test_given_paragraphs_when_chunked_then_offsets_are_exact_nonoverlapping_and_tail_merges():
    from style_fingerprint.corpus import chunk_text, word_count
    text = '\n\n'.join([' '.join(['word'] * n) + '.' for n in [110, 120, 105, 110, 25]])
    chunks = chunk_text(text, 'doc')
    assert len(chunks) == 2
    assert all(100 <= c.word_count <= 700 for c in chunks)
    assert all(text[c.start_char:c.end_char] == c.text and c.document_id == 'doc' for c in chunks)
    assert sum(c.word_count for c in chunks) == word_count(text)
    assert chunks[0].end_char <= chunks[1].start_char


def test_given_huge_paragraph_when_chunked_then_maximum_and_all_words_are_preserved():
    from style_fingerprint.corpus import chunk_text, word_count
    text = ' '.join(['enormous'] * 1600)
    chunks = chunk_text(text, 'big')
    assert len(chunks) >= 3
    assert max(c.word_count for c in chunks) <= 700
    assert sum(c.word_count for c in chunks) == word_count(text)


def test_given_sentences_when_segmented_then_abbreviations_and_offsets_survive():
    from style_fingerprint.corpus import sentence_spans
    text = 'Dr. Smith likes version 3.14. I agree! Do you?'
    spans = sentence_spans(text)
    assert len(spans) == 3
    assert all(text[s['start_char']:s['end_char']] == s['text'] for s in spans)


@pytest.mark.parametrize('contents', [None, '---\ntitle: Empty\n---\n```\ncode\n```'])
def test_given_empty_corpus_or_post_when_ingested_then_clear_error(tmp_path, contents):
    from style_fingerprint.corpus import load_corpus
    if contents is not None:
        (tmp_path / 'empty.md').write_text(contents)
    with pytest.raises(ValueError, match='Markdown|usable prose'):
        load_corpus(tmp_path)
