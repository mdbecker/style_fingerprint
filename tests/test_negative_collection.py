import importlib.util
from pathlib import Path
import json
import pytest


def collector():
    spec = importlib.util.spec_from_file_location('collector', 'scripts/collect_negative_corpus.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_given_blog_html_when_sampled_then_only_author_prose_is_kept():
    module = collector()
    authored = 'I think these neural networks help explain the representation, and we can study their behavior carefully. '
    html = '<nav><p>Navigation junk.</p></nav><div class="post-content"><p>' + authored*4 + '</p><pre>CODE_SECRET</pre><blockquote><p>QUOTED_SECRET</p></blockquote><p>' + authored*8 + '</p></div><footer><p>FOOTER_SECRET</p></footer>'
    prose = module.extract_prose(html, 'html', 'post-content')
    sample = module.sample_prose(prose)
    assert 150 <= len(sample.split()) <= 190
    for excluded in ['Navigation','CODE_SECRET','QUOTED_SECRET','FOOTER_SECRET']:
        assert excluded not in sample
    assert sample.endswith('.')
    assert '\n\n' in sample


def test_given_curated_source_when_collected_then_authorship_and_provenance_are_embedded(tmp_path):
    from style_fingerprint.corpus import load_corpus
    module = collector()
    source = {'author': 'Named Researcher', 'author_id': 'named-researcher', 'title': 'An experiment', 'date': '2019-01-01',
              'source_url': 'https://example.org/experiment/', 'download_url': 'https://example.org/source.md',
              'format': 'markdown', 'repository_revision': 'immutable-commit', 'license': 'excerpt; no redistribution license identified',
              'file': 'named-researcher/2019-01-01-experiment.md'}
    text = 'I think this experiment helps explain the neural network, and we can discuss the practical results carefully. '
    module.collect([source], tmp_path, fetch=lambda url: ('---\ntitle: Original\n---\n\n'+text*15).encode())
    doc = load_corpus(tmp_path)[0]
    assert doc.author == source['author']
    for key in ['author_id','source_url','repository_revision','source_sha256','sample_sha256','retrieved_at','sampling']:
        assert doc.metadata[key]
    assert 150 <= len(doc.clean_text.split()) <= 190
    assert len(json.loads((tmp_path / 'manifest.json').read_text())['documents']) == 1


def test_given_invalid_source_or_existing_changed_sample_when_collected_then_no_overwrite(tmp_path):
    module = collector()
    source = {'author':'Someone','author_id':'someone','title':'Post','date':'2018-01-01','source_url':'https://example.org/post',
              'download_url':'https://example.org/post.md','format':'markdown','file':'someone/post.md','repository_revision':'revision','license':'excerpt'}
    text = ('These careful experiments help us explain the neural network and its important practical behavior. ' * 20).encode()
    module.collect([source], tmp_path, fetch=lambda url: text)
    path = tmp_path / 'someone/post.md'
    path.write_text('User edit')
    with pytest.raises(ValueError, match='overwrite'):
        module.collect([source], tmp_path, fetch=lambda url: text)
    assert path.read_text() == 'User edit'


def test_given_alias_names_with_same_author_id_when_supervised_then_one_author_group(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    from test_supervised import negatives
    root = tmp_path / 'negative_posts'
    negatives(root, 10)
    for i, path in enumerate(sorted(root.glob('*.md'))):
        path.write_text(path.read_text().replace('---\n', '---\nauthor_id: same-person\n', 1).replace('author: Other', f'author: Alias {i} Other'))
    fp = StyleFingerprint.build(corpus, tmp_path / 'artifacts', holdout_fraction=0)
    assert fp.manifest['mode'] == 'supervised'
    assert fp.manifest['negative_grouping'] == 'document'
    assert fp.evaluation['supervised']['negative_author_counts'] == {'same-person': 10}


def test_given_attributed_negatives_when_evaluated_then_author_holdouts_and_sources_are_auditable(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    from test_supervised import negatives
    root = tmp_path / 'negative_posts'
    negatives(root, 12)
    for i,path in enumerate(sorted(root.glob('*.md'))):
        path.write_text(path.read_text().replace('---\n', f'---\nauthor_id: author-{i%3}\nsource_url: https://example.org/post-{i}\n', 1))
    fp = StyleFingerprint.build(corpus, tmp_path / 'artifacts', holdout_fraction=0)
    report = fp.evaluation['supervised']
    assert len(report['negative_author_counts']) == 3
    assert len(report['per_negative_author']) == 3
    for fold in report['folds']:
        assert not set(fold['training_negative_author_ids']) & set(fold['test_negative_author_ids'])
        for inner in fold['inner_folds']:
            assert not set(inner['training_negative_author_ids']) & set(inner['test_negative_author_ids'])
    for row in report['held_out_scores']:
        if row['label'] == 0:
            assert row['author_id'] and row['author'] and row['source_url']


def test_given_licensed_source_with_longer_sample_limit_when_collected_then_length_matches_requested_policy(tmp_path):
    module = collector()
    source = {'author':'Licensed Author','author_id':'licensed-author','title':'Post','date':'2018-01-01',
              'source_url':'https://example.org/post','download_url':'https://example.org/post.md','format':'markdown',
              'file':'licensed-author/post.md','repository_revision':'revision','license':'CC-BY-4.0',
              'maximum_words':600}
    text = ('These careful experiments help us explain the neural network and its important practical behavior. ' * 60).encode()
    rows = module.collect([source], tmp_path, fetch=lambda url: text)
    assert 500 <= rows[0]['excerpt_words'] <= 600


def test_given_html_article_tag_selector_when_extracted_then_distill_prose_survives():
    module = collector()
    assert module.extract_prose('<p>Outside</p><d-article><p>Author prose.</p></d-article>', 'html', 'd-article') == 'Author prose.'


def test_given_latex_math_when_article_extracted_then_equations_do_not_become_style_words():
    module = collector()
    prose = module.extract_prose('<d-article><p>I use $x^2$ carefully. \\(y=3\\) is a variable. $$equation_secret$$ The explanation stays.</p></d-article>', 'html', 'd-article')
    assert 'equation_secret' not in prose and 'x^2' not in prose and 'y=3' not in prose
    assert 'The explanation stays.' in prose


def test_given_one_dominant_negative_author_when_built_then_sampling_bias_is_reported(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    from test_supervised import negatives
    root = tmp_path / 'negative_posts'
    negatives(root, 10)
    for i,path in enumerate(sorted(root.glob('*.md'))):
        text=path.read_text()
        import re
        text=re.sub(r'author: Other \d', 'author: ' + ('Dominant' if i<8 else f'Other {i}'), text)
        path.write_text(text)
    fp=StyleFingerprint.build(corpus,tmp_path / 'artifacts', holdout_fraction=0)
    assert any('dominat' in notice.lower() for notice in fp.manifest['warnings'])


def test_given_edited_author_metadata_when_collection_repeated_then_edit_is_not_silently_accepted(tmp_path):
    module=collector()
    source={'author':'Someone','author_id':'someone','title':'Post','date':'2018-01-01',
            'source_url':'https://example.org/post','download_url':'https://example.org/post.md','format':'markdown',
            'file':'someone/post.md','repository_revision':'revision','license':'CC-BY-4.0'}
    text=('These careful experiments help us explain the neural network and its important practical behavior. '*20).encode()
    module.collect([source],tmp_path,fetch=lambda url:text)
    path=tmp_path/'someone/post.md'
    path.write_text(path.read_text().replace('author: Someone','author: Someone Else'))
    with pytest.raises(ValueError,match='overwrite'):
        module.collect([source],tmp_path,fetch=lambda url:text)


def test_given_author_imbalance_when_evaluated_twice_then_warning_is_not_duplicated(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    from test_supervised import negatives
    import re
    root=tmp_path/'negative_posts'; negatives(root,10)
    for i,path in enumerate(sorted(root.glob('*.md'))):
        path.write_text(re.sub(r'author: Other \d','author: '+('Dominant' if i<8 else f'Other {i}'),path.read_text()))
    fp=StyleFingerprint.build(corpus,tmp_path/'artifacts', holdout_fraction=0)
    fp.evaluate(); fp.evaluate()
    assert len(fp.manifest['warnings']) == len(set(fp.manifest['warnings']))


def test_given_same_margin_distributions_with_different_class_counts_when_calibrated_then_compatibility_scale_is_consistent():
    import numpy as np
    from style_fingerprint.model import fit_calibrator
    small=fit_calibrator(np.array([-2.,-1.,1.,2.]),np.array([0,0,1,1]),42)
    expanded=fit_calibrator(np.array([-2.,-1.]*10+[1.,2.]),np.array([0,0]*10+[1,1]),42)
    inputs=np.array([[-1.5],[0],[1.5]])
    assert expanded.predict_proba(inputs) == pytest.approx(small.predict_proba(inputs),abs=1e-6)


def test_given_rst_proposal_when_extracted_then_headers_code_and_license_are_excluded():
    module=collector()
    body='I think this proposal will make the interface easier to understand, and careful comparisons will help us evaluate the practical behavior. '
    source='PEP: 9999\nTitle: HEADER_SECRET\nAuthor: AUTHOR_SECRET\n\nAbstract\n========\n\n'+body*15+'\n\n.. code-block:: python\n\n    CODE_SECRET\n\n    QUOTED_SECRET\n\nCopyright\n=========\n\nThis document is placed in the public domain.\n'
    prose=module.extract_prose(source,'rst')
    assert body.strip() in prose
    for forbidden in ['HEADER_SECRET','AUTHOR_SECRET','CODE_SECRET','QUOTED_SECRET','Copyright','public domain']:
        assert forbidden not in prose


def test_given_short_negative_length_target_when_collected_then_sentence_complete_short_samples_are_allowed(tmp_path):
    module=collector()
    source={'author':'Someone','author_id':'someone','title':'A proposal','date':'2001-01-01','source_url':'https://example.test/pep','download_url':'https://example.test/pep.rst','format':'rst','file':'someone/pep.md','repository_revision':'abc','license':'public-domain','maximum_words':100,'minimum_words':50}
    raw=('PEP: 9999\nTitle: Test\nAuthor: Someone\n\nAbstract\n========\n\n'+('This careful comparison helps us understand the practical result and decide what we should do next. '*30)).encode()
    rows=module.collect([source],tmp_path,fetch=lambda url:raw)
    assert 50 <= rows[0]['excerpt_words'] <= 100
    assert '50–100' in rows[0]['sampling']
