"""Maintained documentation has a fixed inventory and valid local links."""
from pathlib import Path


def test_given_repository_docs_when_checked_then_inventory_and_links_are_valid():
    from scripts.check_docs import check_documentation
    assert check_documentation(Path(__file__).resolve().parents[1]) == []


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
