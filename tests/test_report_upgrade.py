"""Observable, prose-free evaluation diagnostics."""
from style_fingerprint.report import write_html_report


def test_given_negative_predictions_when_reported_then_authors_and_difficult_roots_are_visible_without_prose(tmp_path):
    # Given development OOF negatives, including a repeated author.
    rows = [dict(author_id='invented-a', root_document_id='negative_posts/easy.md', role='development', source='negative_posts', word_count=320, score=10., raw_margin=-2., embedding=.1, stylometry=.2, character=.3, decision='MISMATCH', text='PRIVATE PROSE'),
            dict(author_id='invented-a', root_document_id='negative_posts/hard.md', role='development', source='negative_posts', word_count=500, score=90., raw_margin=2., embedding=.9, stylometry=.8, character=.7, decision='MATCH'),
            dict(author_id='invented-b', root_document_id='negative_posts/medium.md', role='holdout', source='negative_posts', word_count=400, score=70., raw_margin=1., embedding=.7, stylometry=.6, character=.5, decision='INCONCLUSIVE')]
    evaluation={'negative_diagnostics': rows, 'thresholds': {'match_threshold': 83., 'mismatch_threshold': 42.}}
    manifest={'dataset_counts': {'positive_documents': 4, 'negative_documents': 3, 'training_views': 12}}
    # When HTML is generated.
    path=tmp_path/'report.html'; write_html_report(evaluation, manifest, path)
    html=path.read_text()
    # Then roots and generated observations are distinct, and only diagnostic fields appear.
    assert 'Per-negative-author' in html and 'invented-a' in html
    assert 'Top difficult negative documents' in html
    assert html.index('negative_posts/hard.md') < html.index('negative_posts/easy.md')
    assert 'Generated training views' in html and '>12<' in html
    assert 'Exact match threshold: 83.0' in html and 'Exact mismatch threshold: 42.0' in html
    assert 'PRIVATE PROSE' not in html and 'at 50' not in html


def test_given_operating_metrics_when_reported_then_low_false_acceptance_rates_are_prominent(tmp_path):
    evaluation={'supervised': {'selected_model':'logistic_regression', 'models':{}, 'nested_selection_metrics': {'tpr_at_1pct_fpr': .4, 'tpr_at_5pct_fpr': .6, 'tpr_at_10pct_fpr': .8}}}
    path=tmp_path/'report.html'
    write_html_report(evaluation, {'dataset_counts':{'positive_documents':4,'negative_documents':3}}, path)
    html=path.read_text()
    assert all(label in html for label in ('TPR @ 1% FPR','TPR @ 5% FPR','TPR @ 10% FPR'))


def test_selected_model_operating_point_and_inconclusive_rate_are_visible(tmp_path):
    from style_fingerprint.report import write_html_report
    evaluation={'supervised':{'selected_model':'logistic_regression', 'models':{'logistic_regression':{'auroc':.9}},
                             'metrics':{'inconclusive_rate':.25},'training_performance':{},'nested_selection_metrics':{}}}
    manifest={'dataset_counts':{'positive_documents':20,'negative_documents':20}}
    path=tmp_path/'report.html'
    write_html_report(evaluation,manifest,path)
    html=path.read_text()
    assert 'Selected model development operating point' in html
    assert 'Inconclusive rate' in html
    assert '0.250' in html
