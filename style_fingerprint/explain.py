"""Deterministic measured deviations, analogue retrieval, and bounded deletion."""
import numpy as np
from .corpus import sentence_spans, word_count
from .embeddings import cosine_matrix
from .features import normalize_similarity


def add_explanations(fp, result, clean, passages, embeddings, reference, raw_structure):
    ordered = sorted(result.feature_deviations, key=lambda d: abs(d['robust_z']))
    # Omit fixed-zero features when there are enough meaningful measurements.
    meaningful = [d for d in ordered if d['variable_in_history'] or d['candidate_value'] or d['historical_median']]
    selected = meaningful if len(meaningful) >= 10 else ordered
    result.strongest_matches = selected[:5]
    result.largest_mismatches = sorted(selected, key=lambda d: -abs(d['robust_z']))[:5]
    similarities = cosine_matrix(embeddings, reference['embeddings'])
    passage_scores = []
    for i, passage in enumerate(passages):
        scored = fp.score(passage.text, explain=False, input_format=result.diagnostics['input_format']) if passage.word_count >= 3 else None
        best = float(similarities[i].max())
        passage_scores.append({'passage_id': passage.passage_id, 'text': passage.text,
                               'start_char': passage.start_char, 'end_char': passage.end_char,
                               'score': scored.score if scored is not None else None, 'insufficient_prose': scored is None,
                               'max_reference_similarity': best,
                               'no_close_analogue': normalize_similarity(best, fp.evaluation['calibration']['authorship_embedding']) < .1,
                               'largest_mismatches': sorted(scored.feature_deviations, key=lambda d: -abs(d['robust_z']))[:3] if scored is not None else []})
    result.anomalous_passages = sorted(passage_scores, key=lambda p: p['score'] if p['score'] is not None else -1)[:3]
    # Rank the least compatible passages, then cap all sentence deletion work at twenty.
    if word_count(clean) >= 150:
        all_sentences = sentence_spans(clean)
        inspected = 0
        for passage in result.anomalous_passages:
            for sentence in all_sentences:
                if not (passage['start_char'] <= sentence['start_char'] < passage['end_char']):
                    continue
                if inspected >= 20:
                    break
                without = clean[:sentence['start_char']] + clean[sentence['end_char']:]
                if word_count(without) < 3:
                    continue
                removed_score = fp.score(without, explain=False, input_format=result.diagnostics['input_format'], _raw_structure=raw_structure).score
                inspected += 1
                delta = removed_score - result.score
                if delta > 0:
                    result.anomalous_sentences.append({**sentence, 'sentence': sentence['text'],
                                                       'original_score': result.score, 'score_without': removed_score,
                                                       'delta': delta})
            if inspected >= 20:
                break
        result.anomalous_sentences.sort(key=lambda s: -s['delta'])
        result.diagnostics['sentence_deletions_evaluated'] = inspected
    result.diagnostics['anomaly_note'] = 'Lowest-scoring passages are relative anomalies; deletion deltas measure sensitivity, not causation.'


def add_analogues(fp, result, passages, embeddings, reference):
    similarities = cosine_matrix(embeddings, reference['embeddings'])
    docs = {d.document_id: d for d in fp.documents}
    for i, passage in enumerate(passages):
        for j in np.argsort(-similarities[i], kind='stable')[:3]:
            historical = fp.passages[reference['indices'][int(j)]]
            result.nearest_reference_passages.append({
                'candidate_passage_id': passage.passage_id, 'document_id': historical.document_id,
                'source_file': docs[historical.document_id].source_file, 'passage_id': historical.passage_id,
                'start_char': historical.start_char, 'end_char': historical.end_char,
                'similarity': float(similarities[i,j]), 'excerpt': historical.text[:500]})
