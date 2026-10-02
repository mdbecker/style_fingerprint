"""Combined-source scenarios using invented email content."""
from pathlib import Path
import pytest


def test_given_gmail_when_loaded_then_namespaced_plaintext_positives_keep_source(tmp_path):
    from style_fingerprint.corpus import load_email_corpus
    (tmp_path / 'one.TXT').write_text('Hi Taylor,\n\nI think our next experiment will be interesting!\n\n-- \nSignature')
    docs = load_email_corpus(tmp_path, source='gmail')
    assert len(docs) == 1
    assert docs[0].document_id == 'gmail/one.TXT'
    assert docs[0].metadata['genre'] == 'gmail_email'
    assert 'Signature' not in docs[0].clean_text
    assert docs[0].author == 'Michael Becker'


def test_given_author_credit_in_long_document_when_cleaned_then_it_is_not_mistaken_for_signature():
    from style_fingerprint.corpus import clean_email
    body = ('These experiments help us compare the practical outcomes and understand the next steps.\n' * 30)
    text = 'Project notes\nMichael Becker\nEngineer @ Example\n\n' + body
    assert body.strip() in clean_email(text)
    assert 'Michael Becker' in clean_email(text)


def test_given_three_positive_sources_when_built_then_each_document_has_one_positive_label(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    for source in ['work', 'gmail']:
        root = tmp_path / f'{source}_corpus'; root.mkdir()
        (root / 'synthetic-message.txt').write_text(f'Hello Taylor, I checked the {source} comparison and think we can review the interesting results tomorrow.')
    fp = StyleFingerprint.build(corpus, tmp_path / 'out', holdout_fraction=0)
    assert len(fp.manifest['historical_document_ids']) == 8
    assert fp.manifest['positive_corpus_counts'] == {'blog': 6, 'gmail_email': 1, 'work_email': 1}
    assert {'gmail/synthetic-message.txt','work/synthetic-message.txt'} <= set(fp.manifest['historical_document_ids'])
    assert fp.manifest['positive_training_policy'] == 'single positive class; equal document weight across sources'
    loaded = StyleFingerprint.load(tmp_path / 'out')
    assert loaded.manifest['positive_corpus_counts'] == fp.manifest['positive_corpus_counts']
    assert len(fp.evaluation['folds']) == 8
    assert all(f['candidate_document_id'] not in f['reference_document_ids'] for f in fp.evaluation['folds'])
    only = StyleFingerprint.build(corpus, tmp_path / 'only', work_dir=False, gmail_dir=False, holdout_fraction=0)
    assert len(only.manifest['historical_document_ids']) == 6


def test_given_gmail_cli_override_when_built_then_sources_can_be_enabled_or_disabled(corpus, encoder, tmp_path, capsys):
    from style_fingerprint.cli import main
    root = tmp_path / 'personal'; root.mkdir()
    (root / 'synthetic-message.txt').write_text('Hi Taylor, I think we should discuss this plan together tomorrow. Thanks!')
    assert main(['build', '--no-holdout','--corpus',str(corpus),'--gmail-corpus',str(root),'--artifacts',str(tmp_path/'out')]) == 0
    assert '7 historical documents' in capsys.readouterr().out
    assert main(['build', '--no-holdout','--corpus',str(corpus),'--no-gmail-corpus','--artifacts',str(tmp_path/'only')]) == 0
    assert '6 historical documents' in capsys.readouterr().out


def test_given_private_gmail_when_project_shared_then_ignore_rules_exclude_raw_messages():
    assert '/gmail_corpus/' in Path('.gitignore').read_text().splitlines()


def test_given_negative_scarcity_when_built_then_positive_negative_independent_counts_are_reported(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    fp = StyleFingerprint.build(corpus,tmp_path/'out', holdout_fraction=0)
    assert fp.manifest['dataset_counts'] == {'positive_documents':6,'independent_positives':6,'negative_documents':0,'independent_negatives':0}
