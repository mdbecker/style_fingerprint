"""Small static summary with bounded, collapsed prose-free diagnostics."""
from html import escape
from pathlib import Path
from statistics import mean, median


def write_html_report(evaluation, manifest, path):
    def number(value, exact=False):
        return 'Unavailable' if value is None else (str(value) if exact else f'{value:.3f}')
    def percent(value):
        return 'Unavailable' if value is None else f'{100*value:.1f}'.rstrip('0').rstrip('.')+'%'
    def table(headers, rows):
        return '<table><thead><tr>'+''.join('<th>'+escape(str(h))+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'
    def metrics_table(metrics):
        keys=[('tpr_at_1pct_fpr','TPR @ 1% FPR'),('tpr_at_5pct_fpr','TPR @ 5% FPR'),('tpr_at_10pct_fpr','TPR @ 10% FPR'),('accuracy','Accuracy'),('auroc','AUROC'),('average_precision','Average precision'),('true_positive_rate','Positive acceptance'),('false_positive_rate','Negative acceptance'),('brier','Brier error'),('inconclusive_rate','Inconclusive rate')]
        return table(['Metric','Value'], [(name,number(metrics.get(key))) for key,name in keys])
    supervised=evaluation.get('supervised') or {}
    metrics=supervised.get('metrics') or {}
    holdout=evaluation.get('holdout') or {}
    thresholds=evaluation.get('thresholds') or supervised.get('thresholds') or {}
    match=thresholds.get('match_threshold'); mismatch=thresholds.get('mismatch_threshold')
    negatives=evaluation.get('negative_diagnostics') or []
    def score(row):
        return row.get('compatibility_score', row.get('score', 0))
    def development(row):
        return row.get('split',row.get('role','development')) in {'development','development_oof'}
    # Summary difficulty is based only on development OOF; holdout stays separate.
    dev=[r for r in negatives if development(r)]
    authors={}
    for row in dev:
        if row.get('author_id'):
            authors.setdefault(row['author_id'],[]).append(row)
    author_rows=[]
    for author, rows in authors.items():
        scores=[score(r) for r in rows]
        rate=sum(r.get('decision')=='MATCH' for r in rows)/len(rows)
        author_rows.append((author,len(rows),mean(scores),median(scores),max(scores),rate))
    author_rows.sort(key=lambda r: (-r[5],-r[3],str(r[0])))
    sections='<header><h1>Writing Style Fingerprint</h1><p>Style compatibility compares supplied writing; it is not proof of authorship.</p></header>'
    sections+='<section><h2>Summary</h2><div class="cards">'
    for name,value in [('Recognizes your writing',percent(metrics.get('true_positive_rate'))),('False accepts',percent(metrics.get('false_positive_rate'))),('Inconclusive',percent(metrics.get('inconclusive_rate'))),('AUROC','Unavailable' if metrics.get('auroc') is None else f'{metrics["auroc"]:.2f}')]:
        sections+='<article><strong>'+value+'</strong><span>'+name+'</span></article>'
    sections+='</div><p>Grouped development out-of-fold results.</p></section>'
    sections+='<section><h2>Historical holdout</h2>'
    cm=holdout.get('metrics',{}).get('confusion_matrix')
    if cm and all(cm.get(k) is not None for k in ('true_positive','false_negative','true_negative','false_positive')):
        sections+=f'<p>Your writing: <strong>{cm["true_positive"]} / {cm["true_positive"]+cm["false_negative"]} recognized</strong></p><p>Other technical/email writers: <strong>{cm["true_negative"]} / {cm["true_negative"]+cm["false_positive"]} correctly rejected</strong></p>'
    elif holdout:
        sections+='<p>Holdout decisions are unavailable without calibrated thresholds.</p>'
    else:
        sections+='<p>No mixed-class historical holdout is configured.</p>'
    sections+='<p>This historical holdout has already been inspected and should not be used to tune the model.</p></section>'
    sections+='<section><h2>Decision boundaries</h2>'
    if match is not None:
        sections+=f'<p><strong>MATCH ≥ {match:.0f}</strong></p>'
        if mismatch is not None:
            sections+=f'<p>INCONCLUSIVE {mismatch:.0f}–{match:.0f}</p><p>MISMATCH &lt; {mismatch:.0f}</p>'
        else:
            sections+=f'<p>INCONCLUSIVE_OR_MISMATCH &lt; {match:.0f}</p>'
    else:
        sections+='<p>Learned thresholds are unavailable.</p>'
    sections+='</section>'
    warnings=[]
    if thresholds.get('target_achieved') is False:
        warnings.append('The development false-acceptance target could not be achieved.')
    if match is not None and mismatch is not None and match-mismatch < 1:
        warnings.append('The inconclusive region is extremely narrow; use exact boundaries in Technical details.')
    if author_rows and (author_rows[0][5]>0 or any(r.get('hard_negative') for r in dev)):
        warnings.append('The model still confuses some stylistically similar technical/email writers.')
    if supervised and metrics.get('true_positive_rate') is None:
        warnings.append('Development recognition metrics are unavailable.')
    if not supervised:
        warnings.append('Insufficient independent development data: scoring uses reference similarity.')
    if warnings:
        sections+='<section><h2>Watch-outs</h2>'+''.join('<p>'+w+'</p>' for w in warnings[:3])
        difficult=[r for r in author_rows if r[5]>0 or any(row.get('hard_negative') for row in authors[r[0]])][:3]
        if difficult:
            sections+='<h3>Most difficult other writers</h3>'+table(['Author','False acceptance'],[(r[0],percent(r[5])) for r in difficult])
        sections+='</section>'
    sections+='<details><summary>Technical details</summary>'
    sections+='<h3>Selected model development operating point</h3>'+metrics_table(metrics)
    sections+='<h3>Training fit</h3><p>Optimistic fitting diagnostic, not unseen performance.</p>'+metrics_table(supervised.get('training_performance') or {})
    sections+='<h3>Development cross-validation</h3>'+metrics_table(supervised.get('nested_selection_metrics') or {})
    if supervised.get('ablations'):
        sections+='<h3>Development feature ablation</h3><p>Selected configuration: '+escape(str(supervised.get('selected_configuration','Unavailable')))+'.</p>'
        sections+=table(['Configuration','TPR @ 5% FPR','AUROC','Positive acceptance','Brier error'],[(name,percent((row.get('metrics') or row).get('tpr_at_5pct_fpr')),number((row.get('metrics') or row).get('auroc')),percent((row.get('metrics') or row).get('true_positive_rate')),number((row.get('metrics') or row).get('brier'))) for name,row in supervised['ablations'].items()])
    sections+='<h3>Model comparison</h3>'+table(['Model','AUROC'],[(k,number(v.get('auroc'))) for k,v in supervised.get('models',{}).items()])
    sections+='<p>Final model: '+escape(str(supervised.get('selected_model','reference_similarity')))+'. Exact match threshold: '+number(match,True)+'. Exact mismatch threshold: '+number(mismatch,True)+'.</p>'
    counts=manifest.get('evaluation_dataset_counts') or manifest.get('dataset_counts') or {}
    sections+='<h3>Independent roots and generated views</h3>'+table(['Population','Count'],counts.items())
    views=supervised.get('generated_training_views',counts.get('training_views'))
    if views is not None:
        sections+=f'<p>Generated training views: <strong>{views}</strong>. Views are not independent documents.</p>'
    sections+='<p>Split seed: '+escape(str((manifest.get('holdout_split') or {}).get('seed','Unavailable')))+'.</p>'
    sections+='<h3>Historical holdout operating metrics</h3>'+metrics_table(holdout.get('metrics') or {})
    sections+='<h3>Holdout by source</h3>'+table(['Source','Documents','Positive acceptance','Negative acceptance'],[(source,row.get('count'),percent(row.get('metrics',{}).get('true_positive_rate')),percent(row.get('metrics',{}).get('false_positive_rate'))) for source,row in holdout.get('by_source',{}).items()])
    for source,label in [('email','Negative email authors'),('technical_blog','Negative technical-blog authors')]:
        sections+='<h3>'+label+'</h3>'+table(['Split','Documents','Authors','Median compatibility','False acceptance'],[(split,len(rows),len({r.get('author_id') or r.get('root_document_id') for r in rows}),number(median([score(r) for r in rows])),percent(sum(r.get('decision')=='MATCH' for r in rows)/len(rows))) for split in ('development_oof','historical_holdout') if (rows:=[r for r in negatives if r.get('source_type')==source and development(r)==(split=='development_oof')])])
    sections+='<h3>Per-negative-author performance</h3><p>Development OOF only; complete diagnostics remain in evaluation.json.</p>'+table(['Author','Documents','Mean compatibility','Median compatibility','Maximum compatibility','False acceptance rate'],[(r[0],r[1],number(r[2]),number(r[3]),number(r[4]),percent(r[5])) for r in author_rows[:20]])
    sections+='<h3>Top difficult negative documents</h3><p>Development OOF only; complete rows remain in evaluation_predictions.parquet.</p>'+table(['Document','Author','Source','Words','Compatibility','Margin','Embedding','Stylometry','Character','Decision'],[(r.get('root_document_id','Unavailable'),r.get('author_id','Unknown'),r.get('source_type',r.get('source','Unavailable')),r.get('word_count','Unavailable'),number(score(r)),number(r.get('raw_margin')),number(r.get('embedding_score',r.get('embedding'))),number(r.get('stylometry_score',r.get('stylometry'))),number(r.get('character_score',r.get('character'))),r.get('decision','Unavailable')) for r in sorted(dev,key=lambda r:(-score(r),str(r.get('root_document_id',''))))[:10]])
    sections+='<p>Small source subsets, related correspondence, topic differences and unknown encoder pretraining membership limit generalization. Source categories are diagnostic metadata, never classifier features. No source prose is included here.</p></details>'
    html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Writing Style Fingerprint</title><style>
body{font:16px/1.6 system-ui,sans-serif;background:#f4f6fa;color:#192436;margin:0}main{max-width:1000px;margin:auto;padding:32px 24px}h1{font-size:34px}h2{font-size:23px}section,details{background:white;border:1px solid #dce2ec;border-radius:12px;padding:24px;margin:20px 0;overflow:auto}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:20px}article strong{display:block;font-size:30px;color:#245daf}article span,p{color:#526276}summary{cursor:pointer;font-weight:700;font-size:23px}table{border-collapse:collapse;width:100%;margin:18px 0;font-variant-numeric:tabular-nums}td,th{text-align:left;padding:10px;border-bottom:1px solid #e3e8ef}@media(max-width:700px){.cards{grid-template-columns:repeat(2,1fr)}main{padding:20px 12px}}
</style></head><body><main>'''+sections+'</main></body></html>'
    Path(path).write_text(html,encoding='utf-8')
