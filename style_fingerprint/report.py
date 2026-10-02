"""Standalone aggregate HTML: no raw text, private filenames, or remote assets."""
from html import escape
from pathlib import Path
from statistics import mean, median


def write_html_report(evaluation, manifest, path):
    def number(value):
        return 'Unavailable' if value is None else f'{value:.3f}'
    def metrics_table(metrics):
        keys=[('tpr_at_1pct_fpr','TPR @ 1% FPR'),('tpr_at_5pct_fpr','TPR @ 5% FPR'),('tpr_at_10pct_fpr','TPR @ 10% FPR'),('accuracy','Accuracy at selected match threshold'),('auroc','AUROC'),('average_precision','Average precision'),
              ('true_positive_rate','Positive acceptance at selected match threshold'),('false_positive_rate','Negative acceptance at selected match threshold'),
              ('brier','Brier error (lower is better)'),('inconclusive_rate','Inconclusive rate')]
        return '<table><tbody>'+''.join(f'<tr><th>{name}</th><td>{number(metrics.get(key))}</td></tr>' for key,name in keys)+'</tbody></table>'
    supervised=evaluation.get('supervised',{})
    holdout=evaluation.get('holdout')
    split=manifest.get('holdout_split') or {}
    counts=manifest.get('evaluation_dataset_counts') or manifest['dataset_counts']
    sections=f'''<header><p class="eyebrow">Writing style evaluation</p><h1>How well does the model recognize your writing?</h1>
<p>Style compatibility is a comparison with your supplied writing, not proof of authorship.</p></header>
<div class="cards"><article><strong>{counts['positive_documents']}</strong><span>Independent development positives</span></article>
<article><strong>{counts['negative_documents']}</strong><span>Independent development negatives</span></article>
<article><strong>{holdout['count'] if holdout else 0}</strong><span>Reserved holdout documents</span></article></div>
<p>Split seed: {escape(str(split.get('seed','No seeded holdout')))}. Blogs reserve at least 50%; email and negative target: {escape(str(split.get('fraction','Unavailable')))}. Author and copied-prose groups stay together.</p>'''
    training_views=supervised.get('generated_training_views', counts.get('training_views'))
    if training_views is not None:
        sections+=f'<p>Generated training views: <strong>{training_views}</strong>. Views share their source root and are not independent documents.</p>'
    thresholds=evaluation.get('thresholds') or supervised.get('thresholds') or {}
    sections+='<section><h2>Operating thresholds</h2><p>Match threshold: '+number(thresholds.get('match_threshold'))+'. Mismatch threshold: '+number(thresholds.get('mismatch_threshold'))+'. Thresholds are selected from grouped development out-of-fold root predictions only; intermediate scores are inconclusive.</p></section>'
    if thresholds.get('target_achieved') is False:
        sections+='<p>The development 5% false-acceptance target could not be achieved.</p>'
    if thresholds and thresholds.get('mismatch_threshold') is None:
        sections+='<p>Development data does not support two distinct thresholds; scores below the match threshold return INCONCLUSIVE_OR_MISMATCH.</p>'
    if supervised:
        sections+='<section><h2>Selected model development operating point</h2><p>Grouped out-of-fold root predictions for the final selected model, using the frozen decision thresholds.</p>'+metrics_table(supervised.get('metrics',{}))+'</section>'
        sections+='<div class="grid"><section><h2>Training fit</h2><p>Predictions on development documents used to fit the final model. Optimistic diagnostic; do not use this as an estimate of unseen performance.</p>'+metrics_table(supervised.get('training_performance',{}))+'</section>'
        sections+='<section><h2>Development cross-validation</h2><p>Outer test predictions use model selection and calibration confined to each outer training fold. This measures the selection procedure; the final model choice uses development data only.</p>'+metrics_table(supervised.get('nested_selection_metrics',{}))+'</section></div>'
        sections+='<p>Final model: '+escape(supervised['selected_model'])+'. Individual model comparison AUROC: '+', '.join(escape(k)+': '+number(v['auroc']) for k,v in supervised['models'].items())+'. These comparisons also guide final model selection.</p>'
    else:
        sections+='<section><h2>Training fit / Development cross-validation</h2><p>Supervised metrics unavailable: insufficient independent development data. The model uses reference similarity.</p></section>'
    if holdout:
        sections+='<section><h2>Independent holdout</h2><p>Both classes were reserved before fitting. These predictions never determine fitting, calibration, model selection, or operating thresholds.</p>'+metrics_table(holdout['metrics'])
        cm=holdout['metrics']['confusion_matrix']
        sections+='<h3>Counts at selected match threshold</h3><table><tr><th>Actual writing</th><th>Accepted</th><th>Rejected</th></tr><tr><th>Positive</th><td>'+str(cm['true_positive'])+'</td><td>'+str(cm['false_negative'])+'</td></tr><tr><th>Negative</th><td>'+str(cm['false_positive'])+'</td><td>'+str(cm['true_negative'])+'</td></tr></table>'
        sections+='<h3>Holdout by source</h3><p>Positive acceptance is desirable for your sources. Negative acceptance is an error for negative_posts. Single-class source subsets have no AUROC.</p><table><tr><th>Source</th><th>Documents</th><th>Accuracy</th><th>Positive acceptance</th><th>Negative acceptance</th></tr>'
        for src,row in holdout['by_source'].items():
            m=row['metrics'];sections+=f'<tr><th>{escape(src)}</th><td>{row["count"]}</td><td>{number(m["accuracy"])}</td><td>{number(m["true_positive_rate"])}</td><td>{number(m["false_positive_rate"])}</td></tr>'
        sections+='</table></section>'
    else:
        sections+='<section><h2>Independent holdout</h2><p>No mixed-class holdout is configured. Development results do not substitute for it.</p></section>'
    negatives=evaluation.get('negative_diagnostics', [])
    if negatives:
        authors={}
        for row in negatives:
            if row.get('author_id'):
                authors.setdefault(row['author_id'], []).append(row)
        sections+='<section><h2>Per-negative-author performance</h2><p>Development predictions are out of fold. This author summary combines development and historical holdout diagnostics; it is not an independent performance estimate.</p><table><tr><th>Author</th><th>Documents</th><th>Mean compatibility</th><th>Median compatibility</th><th>Maximum compatibility</th><th>False acceptance rate</th></tr>'
        for author,rows in sorted(authors.items()):
            scores=[r['score'] for r in rows]
            rate=sum(r.get('decision')=='MATCH' for r in rows)/len(rows)
            sections+=f'<tr><th>{escape(str(author))}</th><td>{len(rows)}</td><td>{number(mean(scores))}</td><td>{number(median(scores))}</td><td>{number(max(scores))}</td><td>{number(rate)}</td></tr>'
        sections+='</table></section><section><h2>Top difficult negative documents</h2><p>Ranked by development out-of-fold compatibility. This diagnostic does not alter training weights.</p><table><tr><th>Document</th><th>Author</th><th>Source</th><th>Words</th><th>Compatibility</th><th>Margin</th><th>Embedding</th><th>Stylometry</th><th>Character</th><th>Decision</th></tr>'
        for row in sorted((r for r in negatives if r.get('role','development')=='development'),key=lambda r: (-r['score'], str(r.get('root_document_id','')))):
            sections+='<tr>'+''.join('<td>'+escape(number(row.get(k)) if k in {'score','raw_margin','embedding','stylometry','character'} else str(row.get(k,'Unavailable')))+'</td>' for k in ('root_document_id','author_id','source','word_count','score','raw_margin','embedding','stylometry','character','decision'))+'</tr>'
        sections+='</table></section>'
    sections+='''<aside><h2>How to interpret this report</h2><p>All supplied documents appeared in earlier project experiments. This split is independent of the current fit, but cannot undo earlier exposure. Do not adjust settings using these holdout results; repeated inspection consumes their independence.</p><p>Small source subsets, related email conversations without thread metadata, and topic or genre differences limit generalization. The frozen public encoder’s original training membership is unknown. Evidence length is not certainty about authorship. This report contains aggregate metrics and negative identifiers only; saved model artifacts still contain private source text.</p></aside>'''
    html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Writing style evaluation</title><style>
body{font:16px/1.6 system-ui,sans-serif;background:#f4f6fa;color:#192436;margin:0}main{max-width:1060px;margin:auto;padding:40px 24px}h1{font-size:34px;line-height:1.2;max-width:800px}h2{font-size:23px}.eyebrow{color:#326bc6;font-weight:700}.cards,.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}.grid{grid-template-columns:repeat(2,1fr)}section{overflow:auto}article,section,aside{background:white;border:1px solid #dce2ec;border-radius:12px;padding:24px;margin:20px 0}article strong{display:block;font-size:34px;color:#245daf}article span{display:block;color:#526276}table{border-collapse:collapse;width:100%;margin:18px 0;font-variant-numeric:tabular-nums}td,th{text-align:left;padding:10px;border-bottom:1px solid #e3e8ef}th{font-weight:600}aside{background:#eaf1fc}p{color:#46546a}@media(max-width:700px){.cards,.grid{grid-template-columns:1fr}main{padding:20px 12px}section{overflow:auto}h1{font-size:28px}}
</style></head><body><main>'''+sections+'</main></body></html>'
    Path(path).write_text(html,encoding='utf-8')
