"""Grouped development evaluation, root-level calibration and operating decisions."""
from collections import Counter, defaultdict
from dataclasses import replace
import numpy as np
from .corpus import NEGATIVE_SOURCE_TYPES


def root_id(document):
    return getattr(document, 'root_document_id', None) or document.document_id


def _author_key(document):
    return str(getattr(document,'author_id',None) or (document.metadata or {}).get('author_id') or document.author or '').strip().casefold()


def root_sample_weights(root_ids, labels, author_ids=None, *, hard_negative_authors=None):
    """Equal root influence; known negative authors divide equal influence among roots."""
    authors = list(author_ids) if author_ids is not None else [None] * len(root_ids)
    counts = Counter(root_ids)
    author_roots = defaultdict(set)
    for root, label, author in zip(root_ids, labels, authors):
        if not label and author:
            author_roots[author].add(root)
    # Preserve average negative root mass while balancing known authors.
    known_roots = sum(map(len, author_roots.values()))
    author_mass = known_roots / len(author_roots) if author_roots else 1
    weights = np.array([author_mass / len(author_roots[author]) / counts[root]
                     if not label and author else 1 / counts[root]
                     for root, label, author in zip(root_ids, labels, authors)], dtype=float)
    if hard_negative_authors:
        weights *= [2. if not label and author in hard_negative_authors else 1. for label, author in zip(labels, authors)]
    return weights


def balanced_root_sample_weights(root_ids, labels, author_ids=None, *, hard_negative_authors=None):
    """Balance class mass after hierarchy weighting, independent of sklearn version."""
    weights = root_sample_weights(root_ids, labels, author_ids, hard_negative_authors=hard_negative_authors)
    labels = np.asarray(labels, dtype=int)
    total = weights.sum()
    classes = np.unique(labels)
    for label in classes:
        mask = labels == label
        weights[mask] *= total / (len(classes) * weights[mask].sum())
    return weights


def aggregate_root_predictions(root_ids, margins, labels=None):
    """One median observation per root; missing OOF margins are never fabricated."""
    groups = defaultdict(list)
    root_labels = {}
    for index, (root, margin) in enumerate(zip(root_ids, margins)):
        if np.isfinite(margin):
            groups[root].append(float(margin))
            if labels is not None:
                label = int(labels[index])
                if root in root_labels and root_labels[root] != label:
                    raise ValueError('One root cannot have conflicting labels')
                root_labels[root] = label
    result = {}
    for root, values in groups.items():
        summary = {key: float(value) for key, value in zip(('min','p25','median','p75','max'), np.percentile(values,[0,25,50,75,100]))}
        summary.update(raw_margin=summary['median'], variance=float(np.var(values)), view_count=len(values))
        if labels is not None:
            summary['label'] = root_labels[root]
        result[root] = summary
    return result


def negative_eligibility(root_ids, labels, author_ids=None):
    authors = list(author_ids) if author_ids is not None else [None]*len(root_ids)
    negatives = {root for root,label in zip(root_ids,labels) if not label}
    known = {author for author,label in zip(authors,labels) if not label and author}
    return len(negatives) >= 10 and (not known or len(known) >= 3)


def grouped_splits(labels, root_ids, author_ids=None, *, seed=42, n_splits=3, group_ids=None):
    """Keep positive roots and known negative authors wholly within one fold."""
    from sklearn.model_selection import StratifiedGroupKFold
    labels = np.asarray(labels,dtype=int)
    authors = list(author_ids) if author_ids is not None else [None]*len(labels)
    groups = [f'author:{a}' if not y and a else f'root:{r}' for r,y,a in zip(root_ids,labels,authors)]
    if group_ids is not None:
        groups=list(group_ids)
    count = min(n_splits, *(len({g for g,y in zip(groups,labels) if y == label}) for label in (0,1)))
    if count < 2:
        raise ValueError('Insufficient independent groups for supervised calibration')
    result = list(StratifiedGroupKFold(n_splits=count,shuffle=True,random_state=seed).split(np.zeros(len(labels)),labels,groups))
    if any(len(set(labels[train]))<2 or len({groups[i] for i in train if labels[i]})<2 for train,_ in result):
        buckets = [[],[]]
        assignment = {}
        for label in (0,1):
            for index, group in enumerate(sorted({g for g,y in zip(groups,labels) if y==label})):
                assignment[group] = index%2
        for index,group in enumerate(groups):
            buckets[assignment[group]].append(index)
        result = [(np.array(sorted(set(range(len(labels)))-set(test)),dtype=int),np.array(test,dtype=int)) for test in buckets]
    return result


def group_splits(fp, docs, positive_ids):
    mapping=(fp.manifest.get('holdout_split') or {}).get('document_groups')
    if mapping:
        groups=[mapping.get(root_id(d),mapping.get(d.document_id,root_id(d))) for d in docs]
    else:
        from .holdout import document_groups
        normalized = [replace(d, metadata={**(d.metadata or {}), 'genre': 'blog' if root_id(d) in positive_ids else 'negative_posts'}) for d in docs]
        connected = document_groups(normalized)
        groups = [connected[d.document_id] for d in docs]
    return grouped_splits([int(root_id(d) in positive_ids) for d in docs], [root_id(d) for d in docs],
                          [_author_key(d) for d in docs], seed=fp.config.seed,group_ids=groups)


def choose_verifier(logistic_auc, lightgbm_auc, logistic_tpr5=None, lightgbm_tpr5=None):
    improved = lightgbm_auc is not None and lightgbm_auc - logistic_auc >= .02-1e-12
    preserved = logistic_tpr5 is None or lightgbm_tpr5 is not None and lightgbm_tpr5 >= logistic_tpr5-1e-12
    return 'lightgbm' if improved and preserved else 'logistic_regression'


def select_thresholds(labels,scores,*,target_fpr=.05,target_fnr=.05):
    """Select on development root scores only; thresholds use the scores' own units."""
    labels=np.asarray(labels,dtype=int); scores=np.asarray(scores,dtype=float)
    if len(scores)!=len(labels) or not np.isfinite(scores).all() or set(labels)!={0,1}:
        raise ValueError('Threshold selection needs finite positive and negative development predictions')
    ceiling = 1. if scores.max() <= 1 else 100.
    candidates = np.unique(np.r_[0.,scores,np.minimum(np.nextafter(scores,np.inf),ceiling),ceiling])
    operating=[]
    for threshold in candidates:
        accepted=scores>=threshold
        operating.append((float(np.mean(accepted[labels==0])),float(np.mean(accepted[labels==1])),float(threshold)))
    feasible=[row for row in operating if row[0]<=target_fpr+1e-12]
    achieved=bool(feasible)
    if not feasible:
        best=min(row[0] for row in operating)
        feasible=[row for row in operating if row[0]==best]
    fpr,tpr,match=min(feasible,key=lambda row:(-row[1],row[2]))
    mismatch=None
    reliable = min(np.sum(labels==0),np.sum(labels==1)) >= int(np.ceil(1/min(target_fpr,target_fnr)))
    if reliable:
        lower=[float(t) for t in candidates if t<match
               and not np.isclose(t,match,rtol=1e-9,atol=8*np.finfo(float).eps*ceiling)
               and np.mean(scores[labels==1]<t)<=target_fnr+1e-12]
        if lower:
            mismatch=max(lower)
            # A zero cutoff conveys no supported mismatch region.
            if mismatch <= scores.min():
                mismatch=None
    return {'match_threshold':match,'mismatch_threshold':mismatch,'target_achieved':achieved,
            'target_false_accept_rate':target_fpr,'false_positive_rate':fpr,'true_positive_rate':tpr,
            'limitation':None if achieved else 'The development predictions cannot achieve the 5% false-acceptance target.'}


def decision_for_score(score,match_threshold,mismatch_threshold=None):
    if score>=match_threshold:
        return 'MATCH'
    if mismatch_threshold is None:
        return 'INCONCLUSIVE_OR_MISMATCH'
    return 'MISMATCH' if score<mismatch_threshold else 'INCONCLUSIVE'


def _classification_metrics(labels,scores):
    from sklearn.metrics import roc_auc_score,average_precision_score,roc_curve,brier_score_loss
    labels=np.asarray(labels);scores=np.asarray(scores)
    fpr,tpr,_=roc_curve(labels,scores)
    eer_index=int(np.argmin(abs(fpr-(1-tpr))))
    ece=0.
    for low in np.linspace(0,.9,10):
        mask=(scores>=low)&(scores<low+.1 if low<.9 else scores<=1)
        if mask.any():
            ece+=mask.mean()*abs(labels[mask].mean()-scores[mask].mean())
    result={'auroc':float(roc_auc_score(labels,scores)), 'average_precision':float(average_precision_score(labels,scores)),
            'eer':float((fpr[eer_index]+1-tpr[eer_index])/2),'brier':float(brier_score_loss(labels,scores)), 'calibration_error':float(ece)}
    result.update({f'tpr_at_{n}pct_fpr':float(max(tpr[fpr<=n/100],default=0)) for n in (1,5,10)})
    return result


def performance_report(labels,scores,threshold=None,mismatch_threshold=None):
    labels=np.asarray(labels,dtype=int);scores=np.asarray(scores,dtype=float)
    if threshold is None:
        threshold=select_thresholds(labels,scores)['match_threshold'] if set(labels)=={0,1} else 1.
    predicted=scores>=threshold
    tp=int(np.sum(predicted&(labels==1)));tn=int(np.sum(~predicted&(labels==0)))
    fp=int(np.sum(predicted&(labels==0)));fn=int(np.sum(~predicted&(labels==1)))
    result={'accuracy':float((tp+tn)/len(labels)) if len(labels) else None,
            'true_positive_rate':tp/(tp+fn) if tp+fn else None,'false_positive_rate':fp/(fp+tn) if fp+tn else None,
            'confusion_matrix':{'true_positive':tp,'true_negative':tn,'false_positive':fp,'false_negative':fn},
            'match_threshold':float(threshold),'mismatch_threshold':mismatch_threshold,
            'inconclusive_rate':float(np.mean([decision_for_score(s,threshold,mismatch_threshold).startswith('INCONCLUSIVE') for s in scores])) if len(scores) else None}
    if len(set(labels))==2:
        result.update(_classification_metrics(labels,scores))
    return result


def fold_prediction_rows(root_ids, labels, margins, scores, outer_fold, thresholds):
    """Record outer decisions with thresholds frozen from inner OOF scores."""
    match = thresholds['match_threshold']
    mismatch = thresholds['mismatch_threshold']
    return [dict(root_document_id=root, label=int(label), raw_margin=float(margin),
                 compatibility_score=float(score), decision=decision_for_score(score, match, mismatch),
                 outer_fold=outer_fold, fold_match_threshold=match, fold_mismatch_threshold=mismatch,
                 split='nested_outer')
            for root, label, margin, score in zip(root_ids, labels, margins, scores)]


def nested_performance_report(rows):
    """Aggregate frozen decisions; ranking diagnostics use combined outer scores."""
    labels = np.array([row['label'] for row in rows], dtype=int)
    accepted = np.array([row['decision'] == 'MATCH' for row in rows])
    tp = int(np.sum(accepted & (labels == 1)))
    tn = int(np.sum(~accepted & (labels == 0)))
    fp = int(np.sum(accepted & (labels == 0)))
    fn = int(np.sum(~accepted & (labels == 1)))
    result = dict(accuracy=(tp+tn)/len(rows), true_positive_rate=tp/(tp+fn),
                  false_positive_rate=fp/(fp+tn),
                  confusion_matrix=dict(true_positive=tp, true_negative=tn, false_positive=fp, false_negative=fn),
                  inconclusive_rate=float(np.mean([r['decision'].startswith('INCONCLUSIVE') for r in rows])))
    result.update(_classification_metrics(labels, [r['compatibility_score']/100 for r in rows]))
    return result


def _estimator(kind,seed):
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    if kind=='logistic_regression':
        return make_pipeline(StandardScaler(),LogisticRegression(C=.1,max_iter=2000,random_state=seed,class_weight=None))
    from lightgbm import LGBMClassifier
    return LGBMClassifier(n_estimators=50,num_leaves=7,max_depth=3,min_child_samples=2,learning_rate=.05,random_state=seed,n_jobs=1,verbosity=-1,deterministic=True,force_col_wise=True)


def _margin(estimator,kind,x):
    return np.asarray(estimator.decision_function(x) if kind=='logistic_regression' else estimator.predict(x,raw_score=True))


def _fit_comparison_estimator(kind,seed,x,documents,positive_ids,hard_negative_authors=None):
    labels=[int(root_id(d) in positive_ids) for d in documents]
    weights=root_sample_weights([root_id(d) for d in documents],labels,[_author_key(d) for d in documents],hard_negative_authors=hard_negative_authors)
    balanced_weights=balanced_root_sample_weights([root_id(d) for d in documents],labels,[_author_key(d) for d in documents],hard_negative_authors=hard_negative_authors)
    estimator=_estimator(kind,seed)
    kwargs={'logisticregression__sample_weight':balanced_weights,'standardscaler__sample_weight':weights} if kind=='logistic_regression' else {'sample_weight':balanced_weights}
    return estimator.fit(x,labels,**kwargs)


def fit_calibrator(margins,labels,seed,positive_genres=None):
    from sklearn.linear_model import LogisticRegression
    labels=np.asarray(labels);margins=np.asarray(margins,dtype=float)
    valid=np.isfinite(margins)
    labels=labels[valid];margins=margins[valid]
    if set(labels)!={0,1}:
        raise ValueError('Calibration needs both positive and negative validation examples')
    if positive_genres is not None and len(positive_genres)!=len(valid):
        raise ValueError('Calibration genre labels must match the example count')
    weights=np.array([1/np.sum(labels==y) for y in labels])
    return LogisticRegression(C=1,random_state=seed,tol=1e-10,max_iter=2000).fit(margins.reshape(-1,1),labels,sample_weight=weights)


def fit_root_calibrator(root_ids,margins,labels,seed):
    roots=aggregate_root_predictions(root_ids,margins,labels)
    return fit_calibrator([d['raw_margin'] for d in roots.values()],[d['label'] for d in roots.values()],seed)


def _views(documents,seed):
    from .corpus import generate_training_views
    return [view for document in documents for view in generate_training_views(document,seed=seed)]


def _root_margins(documents,views,margins):
    aggregated=aggregate_root_predictions([root_id(d) for d in views],margins)
    return np.array([aggregated[root_id(d)]['raw_margin'] for d in documents])


def _fold_metadata(documents,train,test,positive_ids):
    return {'training_document_ids':[root_id(documents[i]) for i in train],
            'test_document_ids':[root_id(documents[i]) for i in test],
            'training_negative_author_ids':sorted({_author_key(documents[i]) for i in train if root_id(documents[i]) not in positive_ids and _author_key(documents[i])}),
            'test_negative_author_ids':sorted({_author_key(documents[i]) for i in test if root_id(documents[i]) not in positive_ids and _author_key(documents[i])}),
            'reference_document_ids':[root_id(documents[i]) for i in train if root_id(documents[i]) in positive_ids],
            'negative_reference_document_ids':[root_id(documents[i]) for i in train if root_id(documents[i]) not in positive_ids],
            'negative_reference_author_ids':sorted({_author_key(documents[i]) for i in train if root_id(documents[i]) not in positive_ids and _author_key(documents[i])})}



CONFIGURATIONS = {
    'baseline': {'include_contrast': False, 'include_character': True},
    'contrast': {'include_contrast': True, 'include_character': True},
    'hard_negative_weighting': {'include_contrast': True, 'include_character': True},
    'without_character': {'include_contrast': True, 'include_character': False},
    'hard_negative_weighting_without_character': {'include_contrast': True, 'include_character': False},
}


def choose_configuration(metrics):
    """Adopt only an operational improvement within explicit degradation guards."""
    selected = 'baseline'
    for name in CONFIGURATIONS:
        if name not in metrics or name in {'baseline', 'hard_negative_weighting_without_character'}:
            continue
        candidate, incumbent = metrics[name], metrics[selected]
        comparisons = [incumbent]
        if name in {'hard_negative_weighting', 'without_character'} and 'contrast' in metrics:
            comparisons.append(metrics['contrast'])
        if all(candidate['tpr_at_5pct_fpr'] > reference['tpr_at_5pct_fpr'] + 1e-12
               and candidate['auroc'] >= reference['auroc'] - .01 - 1e-12
               and candidate['true_positive_rate'] >= reference['true_positive_rate'] - .03 - 1e-12
               and candidate['brier'] <= reference['brier'] + 1e-12
               for reference in comparisons):
            selected = name
    if selected == 'hard_negative_weighting' and 'hard_negative_weighting_without_character' in metrics:
        with_character = metrics['hard_negative_weighting']
        without = metrics['hard_negative_weighting_without_character']
        material = (with_character['tpr_at_5pct_fpr'] - without['tpr_at_5pct_fpr'] >= .02 - 1e-12
                    or with_character['auroc'] - without['auroc'] > .01 + 1e-12
                    or with_character['true_positive_rate'] - without['true_positive_rate'] > .03 + 1e-12)
        if not material:
            selected = 'hard_negative_weighting_without_character'
    return selected


def mark_hard_negatives(rows, match_threshold, mismatch_threshold=None):
    """Mark OOF roots only, then summarize difficult authors without holdout input."""
    negatives = [r for r in rows if not r['label'] and r['split'] == 'development_oof']
    cutoff = sorted((r['compatibility_score'] for r in negatives), reverse=True)[max(0, int(np.ceil(len(negatives)*.1))-1)] if negatives else np.inf
    for row in rows:
        row['hard_negative'] = bool(row in negatives and (row['compatibility_score'] >= match_threshold or row['compatibility_score'] >= cutoff))
    authors = {}
    for author in sorted({r.get('author_id') for r in negatives if r.get('author_id')}):
        grouped = [r for r in negatives if r.get('author_id') == author]
        scores = [r['compatibility_score'] for r in grouped]
        authors[author] = {'documents':len(grouped), 'mean_compatibility':float(np.mean(scores)),
            'median_compatibility':float(np.median(scores)), 'maximum_compatibility':max(scores),
            'false_acceptance_rate':float(np.mean([r['decision']=='MATCH' for r in grouped])),
            'hard_negative':bool(any(r['hard_negative'] for r in grouped) or mismatch_threshold is not None and np.median(scores) >= mismatch_threshold)}
    return authors


def source_type_diagnostics(rows):
    result = {}
    for source in NEGATIVE_SOURCE_TYPES:
        grouped=[r for r in rows if not r['label'] and r.get('source_type') == source and r.get('split') == 'development_oof']
        result[source]={'documents':len(grouped), 'authors':len({r['author_id'] for r in grouped if r.get('author_id')}),
            'median_compatibility':float(np.median([r['compatibility_score'] for r in grouped])) if grouped else None,
            'false_acceptance_rate':float(np.mean([r['decision']=='MATCH' for r in grouped])) if grouped else None}
    return result


def _configuration_rows(fp, documents, training_docs, positive_ids, configuration):
    refs=[root_id(d) for d in training_docs if root_id(d) in positive_ids]
    negatives=[root_id(d) for d in training_docs if root_id(d) not in positive_ids]
    cache=getattr(fp, '_evaluation_comparison_cache', None)
    key=(tuple(d.document_id for d in documents),tuple(refs),tuple(negatives))
    if cache is None or key not in cache:
        complete=fp._comparison_rows(documents, refs, negative_reference_ids=negatives)
        if cache is not None:
            cache[key]=complete
    else:
        complete=cache[key]
    x,names=complete
    flags=CONFIGURATIONS[configuration]
    contrast_names={'user_embedding_similarity','best_negative_author_similarity','median_negative_author_similarity','user_vs_best_negative_gap','user_vs_median_negative_gap'}
    retained=[i for i,name in enumerate(names) if (flags['include_contrast'] or name not in contrast_names) and (flags['include_character'] or name!='char_ngram')]
    return x[:,retained],[names[i] for i in retained]


def _training_hard_authors(fp, documents, positive_ids):
    """Single fixed weighting decision from OOF predictions of this training set."""
    if sum(root_id(d) in positive_ids for d in documents) < 3:
        return set()  # Cross-fitting needs two independent positive references after exclusion.
    margins=np.full(len(documents),np.nan)
    labels=np.array([int(root_id(d) in positive_ids) for d in documents])
    try:
        splits=group_splits(fp,documents,positive_ids)
    except ValueError:
        return set()
    for train,test in splits:
        training=[documents[i] for i in train]; testing=[documents[i] for i in test]
        views=_views(training,fp.config.seed); test_views=_views(testing,fp.config.seed)
        x,_=_configuration_rows(fp,views,training,positive_ids,'contrast')
        xt,_=_configuration_rows(fp,test_views,training,positive_ids,'contrast')
        estimator=_fit_comparison_estimator('logistic_regression',fp.config.seed,x,views,positive_ids)
        margins[test]=_root_margins(testing,test_views,_margin(estimator,'logistic_regression',xt))
    calibrator=fit_calibrator(margins,labels,fp.config.seed)
    scores=calibrator.predict_proba(margins.reshape(-1,1))[:,1]*100
    thresholds=select_thresholds(labels,scores)
    rows=[{'root_document_id':root_id(d),'author_id':_author_key(d),'label':int(labels[i]),
           'compatibility_score':float(scores[i]),'split':'development_oof',
                         'decision':decision_for_score(scores[i],thresholds['match_threshold'],thresholds['mismatch_threshold'])} for i,d in enumerate(documents)]
    return {author for author,summary in mark_hard_negatives(rows,thresholds['match_threshold'],thresholds['mismatch_threshold']).items() if summary['hard_negative']}


def run_supervised(fp,negatives):
    """Nested author/root OOF evaluation using weighted views and root calibration."""
    from .corpus import word_count, is_eligible_negative
    negatives=list({d.clean_text:d for d in negatives if is_eligible_negative(d)}.values())
    positives=list({d.clean_text:d for d in fp.documents if root_id(d) in fp.manifest['historical_document_ids']}.values())
    author_counts=Counter(_author_key(d) for d in negatives if _author_key(d))
    if author_counts and max(author_counts.values()) > len(negatives)/2:
        fp.manifest['warnings'].append('One author dominates the negative corpus; balanced author weights limit training influence, but overall metrics may hide poor generalization. Inspect per-author held-out results.')
    if not negative_eligibility([root_id(d) for d in negatives],[0]*len(negatives),[_author_key(d) for d in negatives]) or len(positives)<6:
        if negatives:
            fp.manifest['warnings'].append('Supervised mode requires 10 independent negatives, at least 3 known negative authors when metadata exists, and 6 independent positives; using reference similarity.')
        return
    known_authors={_author_key(d) for d in negatives if _author_key(d)}
    fp.manifest['negative_grouping']='author' if known_authors else 'document'
    docs=positives+negatives
    positive_ids={root_id(d) for d in positives}
    labels=np.array([int(root_id(d) in positive_ids) for d in docs])
    seed=fp.config.seed
    kinds=['logistic_regression']
    try:
        import lightgbm  # noqa: F401
        kinds.append('lightgbm')
    except (ImportError,OSError):
        fp.manifest['warnings'].append('LightGBM unavailable; install the supervised extra and its native OpenMP runtime to compare it with logistic regression.')
    fp._evaluation_comparison_cache={}
    experiments=[(configuration,kind) for configuration in CONFIGURATIONS for kind in kinds]
    predictions={key:np.full(len(docs),np.nan) for key in experiments}
    margins={key:np.full(len(docs),np.nan) for key in experiments}
    nested_rows=[]
    components=np.zeros((len(docs),3))
    contrasts=np.zeros((len(docs),5))
    folds=[]
    for outer_fold,(train,test) in enumerate(group_splits(fp,docs,positive_ids),1):
        train_docs=[docs[i] for i in train];test_docs=[docs[i] for i in test]
        train_views=_views(train_docs,seed);test_views=_views(test_docs,seed)
        inner_splits=group_splits(fp,train_docs,positive_ids)
        inner_margins={key:np.full(len(train_docs),np.nan) for key in experiments}
        outer_hard=_training_hard_authors(fp,train_docs,positive_ids)
        for inner_train,inner_test in inner_splits:
            inner_docs=[train_docs[i] for i in inner_train]
            inner_test_docs=[train_docs[i] for i in inner_test]
            inner_views=_views(inner_docs,seed);inner_test_views=_views(inner_test_docs,seed)
            inner_hard=_training_hard_authors(fp,inner_docs,positive_ids)
            for configuration in CONFIGURATIONS:
                xi,_=_configuration_rows(fp,inner_views,inner_docs,positive_ids,configuration)
                xt,_=_configuration_rows(fp,inner_test_views,inner_docs,positive_ids,configuration)
                for kind in kinds:
                    key=(configuration,kind)
                    estimator=_fit_comparison_estimator(kind,seed,xi,inner_views,positive_ids,inner_hard if configuration in {'hard_negative_weighting', 'hard_negative_weighting_without_character'} else None)
                    inner_margins[key][inner_test]=_root_margins(inner_test_docs,inner_test_views,_margin(estimator,kind,xt))
        inner_metrics={}
        inner_thresholds={}
        for configuration in CONFIGURATIONS:
            x_train,names=_configuration_rows(fp,train_views,train_docs,positive_ids,configuration)
            x_test,_=_configuration_rows(fp,test_views,train_docs,positive_ids,configuration)
            if configuration=='contrast':
                for column,name in enumerate(('authorship_embedding','stylometry','char_ngram')):
                    values=aggregate_root_predictions([root_id(d) for d in test_views],x_test[:,names.index(name)])
                    components[test,column]=[values[root_id(d)]['raw_margin']*100 for d in test_docs]
                for column,name in enumerate(('best_negative_author_similarity','median_negative_author_similarity','user_vs_best_negative_gap','user_embedding_similarity','user_vs_median_negative_gap')):
                    values=aggregate_root_predictions([root_id(d) for d in test_views],x_test[:,names.index(name)])
                    contrasts[test,column]=[values[root_id(d)]['raw_margin'] for d in test_docs]
            for kind in kinds:
                key=(configuration,kind)
                calibrator=fit_calibrator(inner_margins[key],labels[train],seed)
                inner_scores=calibrator.predict_proba(inner_margins[key].reshape(-1,1))[:,1]
                inner_metrics[key]=performance_report(labels[train],inner_scores)
                inner_thresholds[key]=select_thresholds(labels[train],inner_scores*100)
                estimator=_fit_comparison_estimator(kind,seed,x_train,train_views,positive_ids,outer_hard if configuration in {'hard_negative_weighting', 'hard_negative_weighting_without_character'} else None)
                margins[key][test]=_root_margins(test_docs,test_views,_margin(estimator,kind,x_test))
                predictions[key][test]=calibrator.predict_proba(margins[key][test].reshape(-1,1))[:,1]
        inner_models={}
        for configuration in CONFIGURATIONS:
            lr=inner_metrics[(configuration,'logistic_regression')];gb=inner_metrics.get((configuration,'lightgbm'),{})
            inner_models[configuration]=choose_verifier(lr['auroc'],gb.get('auroc'),lr['tpr_at_5pct_fpr'],gb.get('tpr_at_5pct_fpr'))
        nested_configuration=choose_configuration({c:inner_metrics[(c,k)] for c,k in inner_models.items()})
        nested_kind=inner_models[nested_configuration]
        nested_key=(nested_configuration,nested_kind)
        fold_thresholds=inner_thresholds[nested_key]
        nested_rows.extend(fold_prediction_rows([root_id(d) for d in test_docs],labels[test],
                           margins[nested_key][test],predictions[nested_key][test]*100,outer_fold,fold_thresholds))
        fold=_fold_metadata(docs,train,test,positive_ids)
        fold.update(outer_fold=outer_fold,fold_match_threshold=fold_thresholds['match_threshold'],
                    fold_mismatch_threshold=fold_thresholds['mismatch_threshold'],
                    threshold_selection_document_ids=[root_id(d) for d in train_docs],nested_selected_model=nested_kind,nested_selected_configuration=nested_configuration,
                    selection_document_ids=[root_id(d) for d in train_docs],
                    inner_selection_auroc={f'{c}/{k}':metric['auroc'] for (c,k),metric in inner_metrics.items()},
                    test_positive_ids=[root_id(docs[i]) for i in test if labels[i]],
                    calibration_training_ids=[root_id(d) for d in train_docs],
                    negative_reference_document_ids=[root_id(d) for d in train_docs if root_id(d) not in positive_ids],
                    negative_reference_author_ids=sorted({_author_key(d) for d in train_docs if root_id(d) not in positive_ids and _author_key(d)}),
                    hard_negative_weighting_author_ids=sorted(outer_hard),
                    training_view_ids=[d.document_id for d in train_views],test_view_ids=[d.document_id for d in test_views],
                    inner_folds=[_fold_metadata(train_docs,it,iv,positive_ids) for it,iv in inner_splits])
        folds.append(fold)
    experiment_metrics={key:performance_report(labels,prediction) for key,prediction in predictions.items()}
    configuration_models={}
    for configuration in CONFIGURATIONS:
        lr=experiment_metrics[(configuration,'logistic_regression')];gb=experiment_metrics.get((configuration,'lightgbm'),{})
        configuration_models[configuration]=choose_verifier(lr['auroc'],gb.get('auroc'),lr['tpr_at_5pct_fpr'],gb.get('tpr_at_5pct_fpr'))
    ablations={c:{**experiment_metrics[(c,k)],'selected_model':k,**CONFIGURATIONS[c]} for c,k in configuration_models.items()}
    selected_configuration=choose_configuration(ablations)
    selected=configuration_models[selected_configuration]
    selected_key=(selected_configuration,selected)
    model_metrics={kind:experiment_metrics[(selected_configuration,kind)] for kind in kinds}
    views=_views(docs,seed)
    fp.manifest['dataset_counts']['training_views']=len(views)
    x,names=_configuration_rows(fp,views,docs,positive_ids,selected_configuration)
    hard_authors=_training_hard_authors(fp,docs,positive_ids) if selected_configuration in {'hard_negative_weighting', 'hard_negative_weighting_without_character'} else set()
    estimator=_fit_comparison_estimator(selected,seed,x,views,positive_ids,hard_authors)
    calibrator=fit_calibrator(margins[selected_key],labels,seed)
    fp.verifier={'kind':selected,'estimator':estimator,'calibrator':calibrator,'feature_names':names,
                 'selected_configuration':selected_configuration,'hard_negative_authors':sorted(hard_authors)}
    fp.manifest['mode']='supervised';fp.evaluation['mode']='supervised'
    thresholds=select_thresholds(labels,predictions[selected_key]*100)
    fp.evaluation['thresholds']=thresholds
    fp.manifest.update(match_threshold=thresholds['match_threshold'],mismatch_threshold=thresholds['mismatch_threshold'])
    operating=performance_report(labels,predictions[selected_key],threshold=thresholds['match_threshold']/100,
                                 mismatch_threshold=None if thresholds['mismatch_threshold'] is None else thresholds['mismatch_threshold']/100)
    model_metrics[selected].update(operating)
    held_out=[]
    view_counts=Counter(root_id(d) for d in views)
    for index,doc in enumerate(docs):
        score=float(predictions[selected_key][index]*100)
        held_out.append({'document_id':root_id(doc),'root_document_id':root_id(doc),'label':int(labels[index]),
                         'score':score/100,'compatibility_score':score,'raw_margin':float(margins[selected_key][index]),
                         'author':doc.author,'author_id':_author_key(doc),'source_url':(doc.metadata or {}).get('source_url'),
                         'genre':(doc.metadata or {}).get('genre','unknown'),'source':(doc.metadata or {}).get('genre','unknown'),
                         'split':'development_oof','source_type':(doc.metadata or {}).get('source_type'),'word_count':word_count(doc.clean_text),'view_count':view_counts[root_id(doc)],
                         'embedding_score':float(components[index,0]),'stylometry_score':float(components[index,1]),'character_score':float(components[index,2]),
                         'best_negative_author_similarity':float(contrasts[index,0]),'median_negative_author_similarity':float(contrasts[index,1]),'user_vs_best_negative_gap':float(contrasts[index,2]),
                         'user_embedding_similarity':float(contrasts[index,3]),'user_vs_median_negative_gap':float(contrasts[index,4]),
                         'decision':decision_for_score(score,thresholds['match_threshold'],thresholds['mismatch_threshold'])})
    per_author=mark_hard_negatives(held_out,thresholds['match_threshold'],thresholds['mismatch_threshold'])
    fp.evaluation['negative_diagnostics']=[{'role':'development','author_id':row['author_id'],
                                           'root_document_id':row['root_document_id'],'source':row['source'],'word_count':row['word_count'],
                                           'score':row['compatibility_score'],'raw_margin':row['raw_margin'],
                                           'embedding':row['embedding_score'],'stylometry':row['stylometry_score'],'character':row['character_score'],
                                           'decision':row['decision'],'source_type':row['source_type'],'hard_negative':row['hard_negative'],
                                           'best_negative_author_similarity':row['best_negative_author_similarity'],
                                           'median_negative_author_similarity':row['median_negative_author_similarity'],
                                           'user_vs_best_negative_gap':row['user_vs_best_negative_gap']} for row in held_out if not row['label']]
    importance=abs(estimator[-1].coef_[0]).tolist() if selected=='logistic_regression' else estimator.feature_importances_.astype(float).tolist()
    train_root_margins=_root_margins(docs,views,_margin(estimator,selected,x))
    train_scores=calibrator.predict_proba(train_root_margins.reshape(-1,1))[:,1]
    genres=defaultdict(list)
    for index,doc in enumerate(docs):
        if labels[index]:
            genres[(doc.metadata or {}).get('genre','unknown')].append(index)
    fp.evaluation['supervised']={'models':model_metrics,'selected_model':selected,'metrics':model_metrics[selected],'ablations':ablations,'selected_configuration':selected_configuration,
        'per_negative_source_type':source_type_diagnostics(held_out),
        'nested_selection_metrics':nested_performance_report(nested_rows),
        'nested_outer_scores':nested_rows,
        'training_performance':performance_report(labels,train_scores,threshold=thresholds['match_threshold']/100, mismatch_threshold=None if thresholds['mismatch_threshold'] is None else thresholds['mismatch_threshold']/100),
        'cv_method':'Nested stratified root/author cross-validation; root median margins; calibration and threshold selection restricted to outer training folds',
        'calibration_enabled':True,'calibration_class_prior':'equal class mass, one OOF observation per independent root',
        'positive_genre_weighting':'equal root document weight across positive sources','negative_grouping':fp.manifest['negative_grouping'],
        'folds':folds,'selection_margin_auroc':.02,'feature_importance':dict(zip(names,importance)),
        'held_out_scores':held_out,'per_positive_genre':{genre:{'documents':len(indices),
            'mean_compatibility':float(np.mean(predictions[selected_key][indices])*100),
            'accept_rate_at_match_threshold':float(np.mean(predictions[selected_key][indices]*100>=thresholds['match_threshold']))} for genre,indices in genres.items()},
        'negative_author_counts':{author:sum(_author_key(d)==author for d in negatives) for author in sorted(known_authors)},
        'per_negative_author':per_author,'independent_documents':len(docs),'generated_training_views':len(views),
        'limitations':['Model selection and reported metrics share grouped development validation; these are exploratory, not an independent final test.',
                       'Calibration uses root-level out-of-fold margins; no in-sample substitution is permitted.']}
    del fp._evaluation_comparison_cache
