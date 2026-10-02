"""Seeded grouped holdouts are assigned before any fitted preprocessing."""
from dataclasses import replace
from pathlib import Path
import pytest
from style_fingerprint.corpus import Document


def examples():
    docs=[]
    for source,n,label in [('blog',6,1),('work_email',15,1),('gmail_email',10,1),('negative_posts',30,0)]:
        for i in range(n):
            text=f'{source} unique subject {i} with distinct prose.'
            docs.append(Document(f'{source}/{i}',f'/{source}/{i}',text,text,str(i),
                                 f'Author {i//2}' if not label else 'Me',{'genre':source}))
    return docs


def test_given_all_sources_when_seeded_split_then_both_classes_and_half_blogs_are_reserved():
    from style_fingerprint.holdout import split_holdout
    docs=examples();dev,held,info=split_holdout(docs,42,.2)
    assert len([d for d in held if d.metadata['genre']=='blog'])==3
    assert {d.metadata['genre'] for d in held}=={'blog','work_email','gmail_email','negative_posts'}
    assert {d.document_id for d in dev}.isdisjoint(d.document_id for d in held)
    assert len(dev)+len(held)==len(docs)
    assert {d.author for d in dev if d.metadata['genre']=='negative_posts'}.isdisjoint(d.author for d in held if d.metadata['genre']=='negative_posts')
    reordered=split_holdout(list(reversed(docs)),42,.2)
    assert info==reordered[2]
    assert info==split_holdout(docs,42,.2)[2]
    assert info['holdout_document_ids']!=split_holdout(docs,7,.2)[2]['holdout_document_ids']
    assert info['dataset_fingerprint']!=split_holdout(docs+[replace(docs[0],document_id='blog/new')],42,.2)[2]['dataset_fingerprint']


def test_given_duplicate_prose_when_split_then_whole_duplicate_groups_stay_together():
    from style_fingerprint.holdout import split_holdout
    docs=examples();paragraph=' '.join(f'copiedword{i}' for i in range(25))
    docs[6]=replace(docs[6],clean_text=paragraph+'\n\nOther independent message.')
    docs[7]=replace(docs[7],clean_text=paragraph+'\n\nA different message ending.')
    _,_,info=split_holdout(docs,42,.2)
    ids=set(info['holdout_document_ids'])
    assert (docs[6].document_id in ids)==(docs[7].document_id in ids)
    assert info['document_groups'][docs[6].document_id]==info['document_groups'][docs[7].document_id]


def test_given_cross_label_duplicate_when_split_then_bad_labels_fail():
    from style_fingerprint.holdout import split_holdout
    docs=examples();docs[-1]=replace(docs[-1],clean_text=docs[0].clean_text)
    with pytest.raises(ValueError,match='label'): split_holdout(docs,42,.2)


@pytest.mark.parametrize('fraction',[-.1,0,1])
def test_given_invalid_fraction_when_split_then_fail(fraction):
    from style_fingerprint.holdout import split_holdout
    with pytest.raises(ValueError,match='fraction'): split_holdout(examples(),42,fraction)


def test_given_four_blogs_when_split_then_at_least_three_are_reserved():
    from style_fingerprint.holdout import split_holdout
    docs=[d for d in examples() if d.document_id not in {'blog/4','blog/5'}]
    _,held,_=split_holdout(docs,42,.2)
    assert sum(d.metadata['genre']=='blog' for d in held)>=3
