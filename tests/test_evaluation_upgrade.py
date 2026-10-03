import numpy as np
import pytest
from style_fingerprint import evaluation as ev


def test_views_share_equal_root_weight_and_known_authors_share_influence():
    roots = ['p1', 'p2', 'p2', 'a1', 'a2', 'a2', 'b1']
    labels = [1, 1, 1, 0, 0, 0, 0]
    weights = ev.root_sample_weights(roots, labels, [None,None,None,'a','a','a','b'])
    assert weights[0] == pytest.approx(sum(weights[1:3]))
    assert sum(weights[3:6]) == pytest.approx(weights[6])


def test_root_calibration_uses_one_median_and_omits_missing_oof_predictions():
    data = ev.aggregate_root_predictions(['a','a','a','b','c'], [1,2,100,np.nan,-1], [1,1,1,0,0])
    assert list(data) == ['a','c']
    assert data['a']['raw_margin'] == 2
    assert data['a']['view_count'] == 3


def test_validation_never_separates_views_or_known_negative_authors():
    roots = ['p1','p1','p2','p3','n1','n2','n3','n4']
    labels = [1,1,1,1,0,0,0,0]
    authors = [None]*4 + ['a','a','b','c']
    for train, test in ev.grouped_splits(labels,roots,authors,n_splits=2):
        assert not set(np.array(roots)[train]) & set(np.array(roots)[test])
        assert not set(np.array(authors,dtype=object)[train][np.array(labels)[train]==0]) & set(np.array(authors,dtype=object)[test][np.array(labels)[test]==0])


def test_author_diversity_is_required_when_metadata_exists():
    roots = [f'n{i}' for i in range(10)]
    assert not ev.negative_eligibility(roots,[0]*10,['a']*5+['b']*5)
    assert ev.negative_eligibility(roots,[0]*10,['a']*4+['b']*3+['c']*3)
    assert ev.negative_eligibility(roots,[0]*10)


def test_operating_threshold_accepts_most_positives_under_false_acceptance_limit():
    labels = [0]*20+[1]*20
    scores = list(np.linspace(0,.6,20))+list(np.linspace(.5,1,20))
    thresholds = ev.select_thresholds(labels,scores)
    accepted = np.asarray(scores)>=thresholds['match_threshold']
    assert accepted[:20].mean() <= .05
    for threshold in scores:
        candidate=np.asarray(scores)>=threshold
        if candidate[:20].mean()<=.05:
            assert candidate[20:].mean()<=accepted[20:].mean()
    assert ev.decision_for_score(1,**{k:thresholds[k] for k in ('match_threshold','mismatch_threshold')}) == 'MATCH'
    assert ev.decision_for_score(0,thresholds['match_threshold'],thresholds['mismatch_threshold']) == 'MISMATCH'


def test_small_development_set_does_not_claim_two_precise_thresholds():
    thresholds=ev.select_thresholds([0,0,1,1],[.1,.2,.8,.9])
    assert thresholds['mismatch_threshold'] is None
    assert ev.decision_for_score(.1,thresholds['match_threshold']) == 'INCONCLUSIVE_OR_MISMATCH'


def test_challenger_must_preserve_operational_acceptance():
    assert ev.choose_verifier(.8,.83,.8,.7) == 'logistic_regression'
    assert ev.choose_verifier(.8,.82,.8,.8) == 'lightgbm'


def test_report_includes_all_operational_roc_points():
    report=ev.performance_report([0,0,1,1],[.1,.2,.8,.9],threshold=.8)
    assert all(report[f'tpr_at_{n}pct_fpr']==1 for n in (1,5,10))


def test_supervised_evaluation_counts_roots_and_exposes_oof_margin_diagnostics(corpus,encoder,tmp_path):
    from style_fingerprint import StyleFingerprint
    from style_fingerprint.corpus import load_corpus
    for path in corpus.glob('*.markdown'):
        path.write_text(path.read_text()+'\n\n'+(f'An additional independent observation for {path.stem} explains this careful experiment clearly. '*35))
    negative=tmp_path/'inputs'
    negative.mkdir()
    for i in range(12):
        (negative/f'sample-{i}.md').write_text(f'---\nauthor: Writer {i%3}\n---\n'+'\n\n'.join([(f'Buy this offer {i}! Act now! This product delivers immediately! '*35)]*4))
    fp=StyleFingerprint.build(corpus,tmp_path/'artifacts',holdout_fraction=0)
    ev.run_supervised(fp,load_corpus(negative))
    nested=fp.evaluation['supervised']['nested_outer_scores']
    assert len(nested)==18
    for row in nested:
        fold=fp.evaluation['supervised']['folds'][row['outer_fold']-1]
        assert row['root_document_id'] not in fold['threshold_selection_document_ids']
        assert set(fold['threshold_selection_document_ids']) == set(fold['training_document_ids'])
        assert row['decision']==ev.decision_for_score(row['compatibility_score'],row['fold_match_threshold'],row['fold_mismatch_threshold'])
    assert fp.evaluation['supervised']['nested_selection_metrics']==ev.nested_performance_report(nested)
    rows=fp.evaluation['supervised']['held_out_scores']
    expected=ev.select_thresholds([r['label'] for r in rows],[r['compatibility_score'] for r in rows])
    assert fp.evaluation['thresholds']==expected
    exported=fp._prediction_rows()
    assert len([r for r in exported if r['split']=='nested_outer'])==18
    assert len(rows)==18
    assert fp.manifest['dataset_counts']['training_views']==sum(row['view_count'] for row in rows)
    assert all(row['view_count']>1 for row in rows)
    assert all('raw_margin' in row for row in rows)
    assert len(fp.evaluation['negative_diagnostics'])==12
    assert fp.evaluation['thresholds']['match_threshold']==fp.manifest['match_threshold']
    for fold in fp.evaluation['supervised']['folds']:
        assert not set(fold['test_document_ids']) & set(fold['reference_document_ids'])
        assert not set(fold['test_negative_author_ids']) & set(fold['training_negative_author_ids'])


def test_root_calibrator_matches_one_observation_per_available_root():
    roots=['p1','p1','p1','p2','n1','n1','n2','missing']
    margins=[1,2,100,3,-2,-4,-1,np.nan]
    labels=[1,1,1,1,0,0,0,1]
    calibrated=ev.fit_root_calibrator(roots,margins,labels,42)
    expected=ev.fit_calibrator([2,3,-3,-1],[1,1,0,0],42)
    assert calibrated.coef_==pytest.approx(expected.coef_)
    assert calibrated.intercept_==pytest.approx(expected.intercept_)


def test_saturated_negatives_report_unachievable_operating_target():
    result=ev.select_thresholds([0]*20+[1]*20,[1]*3+[.1]*17+[1]*20)
    assert not result['target_achieved']
    assert result['false_positive_rate']==pytest.approx(.15)
    assert result['true_positive_rate']==1
    assert result['limitation']


def test_uncertain_scores_are_inconclusive_without_altering_compatibility():
    assert ev.decision_for_score(.9,.8,.3)=='MATCH'
    assert ev.decision_for_score(.5,.8,.3)=='INCONCLUSIVE'
    assert ev.decision_for_score(.2,.8,.3)=='MISMATCH'


def test_class_balancing_uses_root_mass_instead_of_correlated_view_counts():
    # Given two positive roots, three negative roots, and repeated positive views.
    roots=['p1']*5+['p2','n1','n2','n3']
    labels=[1]*6+[0]*3
    # When class balancing is calculated explicitly before either estimator fits.
    weights=ev.balanced_root_sample_weights(roots,labels)
    # Then both classes have the same mass, and positive roots remain equal.
    assert weights[:6].sum()==pytest.approx(weights[6:].sum())
    assert weights[:5].sum()==pytest.approx(weights[5])
    assert weights.sum()==pytest.approx(5)


def test_repeating_identical_views_of_one_root_preserves_fitted_verifier_margins():
    from style_fingerprint.corpus import Document
    docs=[Document(root,'','Invented prose','Invented prose',root) for root in ['p1','p2','n1','n2','n3']]
    x=np.array([[2.,1.],[1.,2.],[-2.,-1.],[-1.,-2.],[-1.5,-1.]])
    positive_ids={'p1','p2'}
    baseline=ev._fit_comparison_estimator('logistic_regression',42,x,docs,positive_ids)
    repeated_docs=[docs[0]]*5+docs[1:]
    repeated_x=np.vstack([np.repeat(x[:1],5,axis=0),x[1:]])
    repeated=ev._fit_comparison_estimator('logistic_regression',42,repeated_x,repeated_docs,positive_ids)
    assert ev._margin(repeated,'logistic_regression',x)==pytest.approx(ev._margin(baseline,'logistic_regression',x),abs=1e-8)


def test_copied_paragraph_roots_stay_in_same_development_fold_without_holdout():
    from types import SimpleNamespace
    from style_fingerprint.corpus import Document
    from style_fingerprint.config import Config
    shared = ' '.join(f'sharedword{i}' for i in range(25))
    docs=[]
    for i in range(8):
        text=(shared+'\n\n' if i<2 else '')+' '.join(f'original{i}word{j}' for j in range(30))
        docs.append(Document(f'p{i}', 'generic', text, text, str(i), metadata={'genre':'blog'}))
    for i in range(6):
        text=' '.join(f'negative{i}word{j}' for j in range(30))
        docs.append(Document(f'n{i}', 'generic', text, text, str(i), metadata={'genre':'negative_posts','author_id':f'a{i}'}))
    for seed in range(6):
        fp=SimpleNamespace(config=Config(seed=seed),manifest={})
        splits=ev.group_splits(fp, docs, {f'p{i}' for i in range(8)})
        for train,test in splits:
            assert (0 in test) == (1 in test)


def test_two_operating_thresholds_do_not_manufacture_a_machine_precision_inconclusive_band():
    labels=[0]*20+[1]*20
    scores=list(np.linspace(.01,.2,20))+list(np.linspace(.8,1,20))
    thresholds=ev.select_thresholds(labels,scores)
    match=thresholds['match_threshold']; mismatch=thresholds['mismatch_threshold']
    assert mismatch is None or not np.isclose(match,mismatch)
    if mismatch is not None:
        assert np.mean(np.asarray(scores)[20:] < mismatch) <= .05
