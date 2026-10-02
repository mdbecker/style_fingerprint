"""Mixed independent holdout, nested selection, and private HTML reporting."""
import json
from pathlib import Path
import joblib
import pytest


def inputs(tmp_path):
    for folder,n in [('blog_posts',6),('work_corpus',15),('gmail_corpus',10),('negative_posts',30)]:
        root=tmp_path/folder;root.mkdir()
        for i in range(n):
            # Every document has distinct paragraph prose, not merely a different ID.
            text=' '.join(f'{folder}word{i}item{k}' for k in range(60))
            if folder in {'work_corpus','gmail_corpus'}:
                (root/f'{i}.txt').write_text(text)
            else:
                author=f'author: Writer {i//2}\n' if folder=='negative_posts' else ''
                (root/f'{i}.md').write_text('---\n'+author+'title: "<script>bad()</script>"\n---\n'+text)
    return tmp_path/'blog_posts'


def test_given_mixed_sources_when_built_then_holdout_never_enters_fitting_and_report_is_saved(encoder,tmp_path):
    from style_fingerprint import StyleFingerprint
    root=inputs(tmp_path)
    fp=StyleFingerprint.build(root,tmp_path/'bank',holdout_fraction=.2)
    split=fp.manifest['holdout_split']; held=set(split['holdout_document_ids'])
    dev=set(split['development_document_ids'])
    assert held.isdisjoint(dev)
    assert dev=={d.document_id for d in fp.documents}==set(fp.manifest['document_features'])
    assert held.isdisjoint(p.document_id for p in fp.passages)
    for fold in fp.evaluation['supervised']['folds']:
        groups=split['document_groups']
        assert {groups[i] for i in fold['training_document_ids']}.isdisjoint(groups[i] for i in fold['test_document_ids'])
        for field in ['test_document_ids','training_document_ids','reference_document_ids','calibration_training_ids','selection_document_ids']:
            assert set(fold[field])<=dev
        assert set(fold['selection_document_ids'])==set(fold['training_document_ids'])
        assert fold['nested_selected_model'] in fp.evaluation['supervised']['models']
        for inner in fold['inner_folds']:
            assert set(inner['training_document_ids']).isdisjoint(inner['test_document_ids'])
            groups=split['document_groups']
            assert {groups[i] for i in inner['training_document_ids']}.isdisjoint(groups[i] for i in inner['test_document_ids'])
    report=fp.evaluation['holdout']
    assert {r['label'] for r in report['documents']}=={0,1}
    assert set(report['by_source'])=={'blog','work_corpus','gmail_corpus','negative_posts'}
    assert report['by_source']['blog']['count']>=3
    assert {'auroc','accuracy','false_positive_rate','true_positive_rate','confusion_matrix'}<=report['metrics'].keys()
    assert sum(report['metrics']['confusion_matrix'].values())==len(held)
    assert {'training_performance','nested_selection_metrics'}<=fp.evaluation['supervised'].keys()
    model_hash=joblib.hash(fp.verifier)
    assert fp._evaluate_holdout()==report
    assert joblib.hash(fp.verifier)==model_hash
    loaded=StyleFingerprint.load(tmp_path/'bank')
    assert loaded.evaluation['holdout']==report and loaded.manifest['holdout_split']==split
    html=(tmp_path/'bank'/'report.html').read_text()
    assert all(x in html for x in ['Training fit','Development cross-validation','Independent holdout','blog','gmail_corpus','work_corpus','negative_posts'])
    assert '<script>bad()' not in html
    assert not any(d.clean_text in html for d in fp.documents)
    assert str(tmp_path) not in html


def test_given_seed_flag_when_cli_builds_then_manifest_and_html_record_it(encoder,tmp_path,capsys):
    from style_fingerprint.cli import main
    root=inputs(tmp_path)
    assert main(['build','--corpus',str(root),'--artifacts',str(tmp_path/'bank'),'--seed','7','--holdout-fraction','.2'])==0
    manifest=json.loads((tmp_path/'bank'/'manifest.json').read_text())
    assert manifest['holdout_split']['seed']==7
    assert 'report.html' in capsys.readouterr().out
