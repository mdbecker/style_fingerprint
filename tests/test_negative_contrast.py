from style_fingerprint import evaluation as ev


def test_hard_roots_use_only_development_oof_and_include_top_decile_or_matches():
    rows=[dict(root_document_id=str(i), author_id=f'a{i}', source_type='email' if i%2 else 'technical_blog', label=0, compatibility_score=i, split='development_oof',decision='MISMATCH') for i in range(20)]
    rows += [dict(root_document_id='holdout',author_id='sealed',label=0,compatibility_score=100,split='historical_holdout',decision='MATCH')]
    authors=ev.mark_hard_negatives(rows, match_threshold=16, mismatch_threshold=14)
    assert {r['root_document_id'] for r in rows if r['hard_negative']} == {'16','17','18','19'}
    assert 'sealed' not in authors
    assert authors['a14']['hard_negative']
    assert not authors['a13']['hard_negative']
    assert ev.source_type_diagnostics(rows)['email']['documents'] == 10


def test_top_decile_includes_at_least_one_root_without_accepted_negatives():
    rows=[dict(root_document_id=str(i),author_id='a',label=0,compatibility_score=i,split='development_oof',decision='MISMATCH') for i in range(3)]
    ev.mark_hard_negatives(rows,10,None)
    assert [r['root_document_id'] for r in rows if r['hard_negative']] == ['2']
