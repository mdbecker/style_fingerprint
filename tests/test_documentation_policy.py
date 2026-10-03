"""Maintained documentation has a fixed inventory and valid local links."""
from pathlib import Path


def test_given_repository_docs_when_checked_then_inventory_and_links_are_valid():
    from scripts.check_docs import check_documentation
    assert check_documentation(Path(__file__).resolve().parents[1]) == []


def test_given_synthetic_generation_guide_when_maintained_then_it_has_inventory_and_entry_points():
    from scripts.check_docs import MAINTAINED_DOCS
    root = Path(__file__).resolve().parents[1]
    assert 'synthetic-generation.md' in MAINTAINED_DOCS
    assert (root / 'docs/synthetic-generation.md').is_file()
    for name in ('README.md', 'negative-corpus.md'):
        assert '(synthetic-generation.md)' in (root / 'docs' / name).read_text()


def scaffold(root):
    from scripts.check_docs import MAINTAINED_DOCS
    (root/'docs').mkdir()
    for name in MAINTAINED_DOCS:
        (root/'docs'/name).write_text('{}' if name.endswith('.json') else '# Example\n')
    (root/'README.md').write_text('[Docs](docs/README.md)\n')
    (root/'AGENTS.md').write_text('[Spec](docs/specification.md)\n')


def test_given_generated_or_extra_document_when_checked_then_it_is_rejected(tmp_path):
    from scripts.check_docs import check_documentation
    scaffold(tmp_path)
    (tmp_path/'docs'/'green-sample.txt').write_text('sample')
    (tmp_path/'docs'/'task-notes.md').write_text('sample')
    errors=check_documentation(tmp_path)
    assert any('transcript' in e for e in errors)
    assert any('task-notes.md' in e for e in errors)


def test_given_broken_file_or_heading_link_when_checked_then_it_is_rejected(tmp_path):
    from scripts.check_docs import check_documentation
    scaffold(tmp_path)
    (tmp_path/'docs'/'README.md').write_text('[Missing](absent.md)\n[Heading](specification.md#missing)\n')
    errors=check_documentation(tmp_path)
    assert any('absent.md' in e for e in errors)
    assert any('#missing' in e for e in errors)


def test_given_valid_links_and_code_examples_when_checked_then_it_passes(tmp_path):
    from scripts.check_docs import check_documentation
    scaffold(tmp_path)
    (tmp_path/'docs'/'README.md').write_text('[Heading](specification.md#example)\n[External](https://example.test)\n```md\n[Example](nonexistent.md)\n```\n')
    assert check_documentation(tmp_path)==[]


def test_given_synthetic_policy_when_documented_then_old_prohibition_is_superseded():
    root = Path(__file__).resolve().parents[1]
    for name in ('specification.md', 'negative-corpus.md', 'corpus.md', 'implementation.md'):
        text = (root / 'docs' / name).read_text()
        assert 'ai_synthetic' in text
        assert 'Only human-authored other-author' not in text
    policy = (root / 'docs/negative-corpus.md').read_text()
    assert 'blind' in policy and 'transitive' in policy and 'T30' in policy
