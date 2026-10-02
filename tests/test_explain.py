
def test_given_different_style_when_explained_then_measurable_matches_and_mismatches(fingerprint):
    result = fingerprint.score(('Operational requirements are satisfied. Results are delivered. Compliance is mandated! ' * 60))
    assert len(result.strongest_matches) == 5
    assert len(result.largest_mismatches) == 5
    for item in result.largest_mismatches:
        assert {'feature','candidate_value','historical_mean','historical_median','historical_std','robust_z','historical_percentile','description'} <= item.keys()
    assert result.diagnostics['contributions']


def test_given_one_different_passage_when_explained_then_that_passage_and_bounded_sentences_surface(fingerprint, corpus):
    familiar = fingerprint.documents[0].clean_text
    strange = 'BUY NOW! WIN BIG! ACT FAST! ' * 45
    result = fingerprint.score(familiar + '\n\n' + strange)
    assert 'BUY NOW' in result.anomalous_passages[0]['text']
    assert len(result.anomalous_passages) <= 3
    assert len(result.anomalous_sentences) <= 20
    assert result.diagnostics['sentence_deletions_evaluated'] <= 20
    for s in result.anomalous_sentences:
        assert s['delta'] == s['score_without'] - s['original_score']


def test_given_familiar_text_when_scored_then_top_three_analogues_identify_sources(fingerprint):
    result = fingerprint.score(fingerprint.documents[0].clean_text)
    assert result.nearest_reference_passages
    for passage in result.nearest_reference_passages:
        assert passage['document_id'] in {d.document_id for d in fingerprint.documents}
        assert passage['source_file'].endswith('.markdown')
        assert passage['excerpt'] and -1 <= passage['similarity'] <= 1
    counts = {}
    for p in result.nearest_reference_passages:
        counts[p['candidate_passage_id']] = counts.get(p['candidate_passage_id'], 0) + 1
    assert max(counts.values()) <= 3
