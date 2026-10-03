from style_fingerprint.report import write_html_report


def render(tmp_path, negatives=()):
    evaluation = {'supervised': {'selected_model': 'logistic_regression', 'models': {},
        'metrics': {'true_positive_rate': .981, 'false_positive_rate': .05, 'inconclusive_rate': .01, 'auroc': .991},
        'nested_selection_metrics': {'true_positive_rate': .887, 'false_positive_rate': .057, 'inconclusive_rate': .065, 'auroc': .97},
        'training_performance': {'auroc': 1.}},
        'thresholds': {'match_threshold': 39.123456, 'mismatch_threshold': 38.123456},
        'holdout': {'count': 36, 'metrics': {'auroc': .878, 'confusion_matrix': {'true_positive': 15, 'false_negative': 1, 'true_negative': 11, 'false_positive': 9}}, 'by_source': {}},
        'negative_diagnostics': list(negatives)}
    path = tmp_path / 'report.html'
    write_html_report(evaluation, {'dataset_counts': {'positive_documents': 20, 'negative_documents': 20}}, path)
    return path.read_text()


def test_given_operating_metrics_when_reported_then_summary_is_readable_and_details_are_collapsed(tmp_path):
    html = render(tmp_path)
    visible = html.split('<details')[0]
    assert '<h2>Summary</h2>' in visible
    assert 'Recognizes your writing' in visible and '88.7%' in visible
    assert '5.7%' in visible and '6.5%' in visible and '0.97' in visible
    assert '98.1%' not in visible
    assert 'Estimated using grouped cross-validation of the complete model-selection process.' in visible
    assert 'Selected configuration OOF performance' in html and '0.981' in html
    assert '15 / 16 recognized' in visible and '11 / 20 correctly rejected' in visible
    assert '<h2>Historical holdout</h2>' in visible and '<h2>Decision boundaries</h2>' in visible
    assert '≥ 39' in visible and '38–39' in visible and '39.123456' not in visible
    assert 'Training fit' not in visible
    assert '<summary>Technical details</summary>' in html and '<details open' not in html
    assert 'already been inspected' in visible


def test_given_many_negative_authors_when_reported_then_tables_are_bounded_and_sources_remain_diagnostic(tmp_path):
    rows = [dict(author_id=f'invented-{i:02}', root_document_id=f'root-{i:02}', source_type='email' if i%2 else 'technical_blog', split='development_oof', score=90-i, decision='MATCH') for i in range(30)]
    html = render(tmp_path, rows)
    visible, technical = html.split('<details', 1)
    assert sum(f'invented-{i:02}' in visible for i in range(30)) <= 3
    assert sum(f'invented-{i:02}' in technical for i in range(30)) <= 20
    assert sum(f'root-{i:02}' in technical for i in range(30)) == 10
    assert 'Negative email authors' in technical and 'Negative technical-blog authors' in technical
    assert 'Median compatibility' in technical and 'False acceptance' in technical


def test_given_uncalibrated_holdout_when_reported_then_missing_decision_counts_are_explained(tmp_path):
    evaluation = {'holdout': {'metrics': {'confusion_matrix': dict.fromkeys(('true_positive','false_negative','true_negative','false_positive'))}}}
    path = tmp_path / 'fallback.html'
    write_html_report(evaluation, {'dataset_counts': {}}, path)
    html = path.read_text()
    assert 'Holdout decisions are unavailable without calibrated thresholds.' in html
    assert 'scoring uses reference similarity' in html


def test_given_development_ablations_when_reported_then_selection_is_available_inside_details(tmp_path):
    path = tmp_path / 'ablations.html'
    evaluation = {'supervised': {'selected_configuration':'without_character', 'ablations': {'baseline': {'metrics': {'auroc': .8}}, 'without_character': {'metrics': {'auroc': .9}}}}}
    write_html_report(evaluation, {'dataset_counts': {}}, path)
    visible, technical = path.read_text().split('<details', 1)
    assert 'without_character' not in visible
    assert 'Development feature ablation' in technical and 'without_character' in technical
