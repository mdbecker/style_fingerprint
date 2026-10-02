"""Reproducible source-stratified, authorship/prose-group-disjoint holdouts."""
import hashlib
import json
import math
import random
from .corpus import word_count


def source(doc):
    genre=(doc.metadata or {}).get('genre','blog')
    return {'work_email':'work_corpus','gmail_email':'gmail_corpus','blog':'blog'}.get(genre,'negative_posts')


def label(doc):
    return int(source(doc)!='negative_posts')


def document_groups(documents):
    docs=sorted(documents,key=lambda d:d.document_id)
    parents={d.document_id:d.document_id for d in docs}
    def find(key):
        while parents[key]!=key:
            parents[key]=parents[parents[key]];key=parents[key]
        return key
    def union(a,b):
        a,b=find(a),find(b);parents[max(a,b)]=min(a,b)
    seen={}
    for d in docs:
        keys=['root:' + d.root_document_id, 'body:'+ ' '.join(d.clean_text.split())]
        keys+=['paragraph:'+' '.join(p.split()) for p in d.clean_text.split('\n\n') if word_count(p)>=20]
        if not label(d):
            author=str(d.author_id or '').strip().casefold()
            if author: keys.append('author:'+author)
        for key in keys:
            if key in seen: union(d.document_id,seen[key])
            else: seen[key]=d.document_id
    groups={d.document_id:find(d.document_id) for d in docs}
    for group in set(groups.values()):
        if len({label(d) for d in docs if groups[d.document_id]==group})>1:
            raise ValueError('Duplicate prose crosses positive/negative labels; review corpus attribution.')
    return groups


def split_holdout(documents,seed=42,fraction=.2):
    if not 0<fraction<1: raise ValueError('Holdout fraction must be between zero and one.')
    docs=sorted(documents,key=lambda d:d.document_id)
    groups=document_groups(docs)
    selected=set()
    for stratum in ['blog','work_corpus','gmail_corpus','negative_posts']:
        rows=[d for d in docs if source(d)==stratum]
        if not rows: continue
        candidates=sorted({groups[d.document_id] for d in rows})
        random.Random(f'{seed}:{stratum}').shuffle(candidates)
        target=min(len(rows),max(3,math.ceil(len(rows)*.5))) if stratum=='blog' else math.ceil(len(rows)*fraction)
        for group in candidates:
            if sum(groups[d.document_id] in selected for d in rows)>=target: break
            selected.add(group)
    held=[d for d in docs if groups[d.document_id] in selected]
    dev=[d for d in docs if groups[d.document_id] not in selected]
    if {label(d) for d in held}!={0,1} or {label(d) for d in dev}!={0,1}:
        raise ValueError('Group-disjoint holdout requires both labels in development and holdout; add independent groups or explicitly disable holdout for diagnostics.')
    fingerprint=hashlib.sha256(json.dumps([(d.document_id,d.file_hash,hashlib.sha256(d.clean_text.encode()).hexdigest(),source(d),d.author,(d.metadata or {}).get('author_id')) for d in docs],sort_keys=True).encode()).hexdigest()
    info={'version':'seeded-source-groups-v1','seed':seed,'fraction':fraction,'blog_fraction':.5,
          'dataset_fingerprint':fingerprint,'document_groups':groups,
          'development_document_ids':[d.document_id for d in dev],
          'holdout_document_ids':[d.document_id for d in held]}
    return dev,held,info
