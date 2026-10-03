import numpy as np
import pytest
from style_fingerprint import evaluation as ev
from style_fingerprint.report import write_html_report


def test_given_inner_scores_when_outer_labels_change_then_frozen_thresholds_and_decisions_do_not():
    inner_labels = [0]*20 + [1]*20
    inner_scores = np.r_[np.linspace(10, 40, 20), np.linspace(35, 90, 20)]
    thresholds = ev.select_thresholds(inner_labels, inner_scores)
    rows = ev.fold_prediction_rows(['a', 'b'], [0, 1], [-1, 1], [30, 70], 1, thresholds)
    changed = ev.fold_prediction_rows(['a', 'b'], [1, 0], [-1, 1], [30, 70], 1, thresholds)
    assert [r['decision'] for r in rows] == [r['decision'] for r in changed]
    assert all(r['fold_match_threshold'] == thresholds['match_threshold'] for r in changed)


def test_given_different_fold_thresholds_when_aggregated_then_existing_decisions_define_metrics():
    first = ev.fold_prediction_rows(['a','b'], [1,0], [1,0], [60,55], 1,
                                    {'match_threshold':50, 'mismatch_threshold':20})
    second = ev.fold_prediction_rows(['c','d'], [1,0], [1,0], [60,55], 2,
                                     {'match_threshold':80, 'mismatch_threshold':65})
    rows = first + second
    metrics = ev.nested_performance_report(rows)
    assert [r['decision'] for r in rows] == ['MATCH','MATCH','MISMATCH','MISMATCH']
    assert metrics['true_positive_rate'] == .5
    assert metrics['false_positive_rate'] == .5
    assert metrics['accuracy'] == .5
    assert metrics['inconclusive_rate'] == 0
    ranking = ev.performance_report([1,0,1,0], [.6,.55,.6,.55], threshold=.99)
    for key in ('auroc','average_precision','brier','tpr_at_1pct_fpr','tpr_at_5pct_fpr','tpr_at_10pct_fpr'):
        assert metrics[key] == pytest.approx(ranking[key])
    rows[2]['decision'] = 'INCONCLUSIVE'
    assert ev.nested_performance_report(rows)['inconclusive_rate'] == .25


def test_given_unstable_fold_thresholds_when_reported_then_warning_is_technical_only(tmp_path):
    rows = ev.fold_prediction_rows(['a','b'], [1,0], [1,-1], [80,10], 1,
                                   {'match_threshold':40, 'mismatch_threshold':None})
    rows += ev.fold_prediction_rows(['c','d'], [1,0], [1,-1], [80,10], 2,
                                    {'match_threshold':60, 'mismatch_threshold':20})
    metrics = ev.nested_performance_report(rows)
    path = tmp_path/'report.html'
    write_html_report({'supervised': {'nested_selection_metrics':metrics,
        'nested_outer_scores':rows, 'metrics':{'true_positive_rate':.123}}}, {}, path)
    visible, technical = path.read_text().split('<details',1)
    assert '100%' in visible and '12.3%' not in visible
    assert 'complete model and threshold-selection process' in visible
    assert 'Nested selection performance' in technical
    assert 'Selected configuration OOF performance' in technical
    assert 'Match threshold range' in technical
    warning = 'Threshold estimates vary substantially across development folds, indicating limited calibration stability.'
    assert warning in technical and warning not in visible
