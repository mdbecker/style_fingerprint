"""Behavioral coverage for domain-matched, human negative sources."""
import pytest
from style_fingerprint import corpus


def write(root, relative, metadata, body='I explain this neural network carefully and compare the practical results.'):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('---\n' + metadata + '\n---\n\n' + body)


@pytest.mark.parametrize('metadata,relative', [
    ('source_type: specification', 'other/post.md'),
    ('source_type: technical_blog\nsource_url: https://peps.python.org/pep-0008/', 'other/post.md'),
    ('author_id: pep-someone', 'other/post.md'),
    ('source_type: technical_blog', 'python-peps/pep-9999.md'),
    ('source_type: api_documentation', 'other/post.md'),
    ('source_type: technical_blog\nhuman_authored: false', 'other/post.md'),
])
def test_given_ineligible_prose_when_negatives_loaded_then_it_is_excluded(tmp_path, metadata, relative):
    write(tmp_path, relative, metadata)
    assert corpus.load_negative_corpus(tmp_path) == []


def test_given_email_and_blog_when_loaded_then_types_and_author_groups_are_retained(tmp_path):
    write(tmp_path, 'email/alice/one.md', 'author: Alice\nauthor_id: alice')
    write(tmp_path, 'email/alice/two.txt', 'author: Alice\nauthor_id: alice')
    write(tmp_path, 'blogs/bob/post.md', 'author: Bob\nauthor_id: bob')
    docs = corpus.load_negative_corpus(tmp_path)
    assert len(docs) == 3
    assert {doc.source_type for doc in docs} == {'email', 'technical_blog'}
    assert [doc.author_id for doc in docs].count('alice') == 2
    assert all(doc.root_document_id for doc in docs)
    assert all(doc.metadata['source_type'] == doc.source_type for doc in docs)


def test_given_negative_email_boilerplate_when_loaded_then_only_new_prose_remains(tmp_path):
    body = 'From: alice@example.org\nTo: bob@example.org\nDate: yesterday\nSubject: Update\n\n<p>I examined the model and I think the error deserves another experiment.</p>\n> OLD_SECRET quoted message\n\nBest regards,\nAlice\nSenior Engineer\nLEGAL_SECRET This email is confidential.'
    write(tmp_path, 'email/alice/message.md', 'author: Alice', body)
    text = corpus.load_negative_corpus(tmp_path)[0].clean_text
    assert 'I examined the model' in text
    for value in ['OLD_SECRET', 'LEGAL_SECRET', 'Senior Engineer', 'alice@example', '<p>', 'yesterday', 'Best regards']:
        assert value not in text


def test_given_forwarded_email_when_loaded_then_forwarded_content_is_removed(tmp_path):
    write(tmp_path, 'email/alice/message.md', 'author: Alice', 'I made a careful comparison of the two models.\n\nBegin forwarded message:\nFrom: bob@example.org\nFORWARD_SECRET prose')
    assert 'FORWARD_SECRET' not in corpus.load_negative_corpus(tmp_path)[0].clean_text


def test_given_headerless_formal_proposal_when_loaded_then_it_is_not_negative_prose(tmp_path):
    write(tmp_path, 'old/post.md', 'author: Other', 'PEP: 9999\nTitle: Proposal\nAuthor: Other\n\nAbstract\n========\nI propose a formal language interface specification.')
    assert corpus.load_negative_corpus(tmp_path) == []


def test_given_html_email_decoration_when_cleaned_then_paragraph_prose_is_preserved(tmp_path):
    write(tmp_path, 'email/alice/message.md', 'author: Alice', '<html><style>STYLE_SECRET</style><p>I tested the architecture carefully.</p><blockquote>QUOTE_SECRET</blockquote><p>The comparison gave useful evidence.</p><div>Sent from my phone</div></html>')
    text = corpus.load_negative_corpus(tmp_path)[0].clean_text
    assert 'I tested the architecture carefully.' in text
    assert 'The comparison gave useful evidence.' in text
    assert 'STYLE_SECRET' not in text and 'QUOTE_SECRET' not in text


def test_given_unattributed_roots_when_loaded_then_filenames_do_not_invent_known_writers(tmp_path):
    write(tmp_path, 'one.md', '')
    write(tmp_path, 'two.md', '')
    docs = corpus.load_negative_corpus(tmp_path)
    assert all(doc.author_id is None for doc in docs)


def test_given_nested_author_and_explicit_identity_when_loaded_then_identity_is_respected(tmp_path):
    write(tmp_path, 'blogs/alice/one.md', '')
    write(tmp_path, 'blogs/alice/two.md', 'author_id: canonical-alice')
    docs = corpus.load_negative_corpus(tmp_path)
    assert [doc.author_id for doc in docs] == ['alice', 'canonical-alice']


def test_given_direct_legacy_document_when_eligibility_checked_then_body_and_provenance_are_checked():
    doc = corpus.Document('other/post.md', '', '', 'PEP: 9999\nFormal proposal prose', '', metadata={'source_type': 'technical_blog'})
    assert not corpus.is_eligible_negative(doc)
    doc.clean_text = 'I explained this model carefully.'
    assert corpus.is_eligible_negative(doc)
    doc.metadata['source_url'] = 'https://peps.python.org/pep-9999/'
    assert not corpus.is_eligible_negative(doc)


def test_given_negative_email_with_code_and_wrapped_quote_markers_when_cleaned_then_only_human_prose_remains():
    from style_fingerprint.corpus import clean_negative_email
    authored='I compared the numerical algorithm carefully and explained the practical tradeoffs.'
    raw=authored+'\n\nwrote:\n>>> run_model()\n@jit(nopython=True)\ndef example():\n    array[0] = result[1]; value = array[0]\n\n```python\nsecret_code()\n```\n\n'+authored
    clean=clean_negative_email(raw)
    assert clean.count(authored)==2
    for code in ['wrote:','run_model','@jit','def example','array[0]','secret_code']:
        assert code not in clean
