"""Compact, interpretable stylometry and reference-based score normalization."""
from collections import Counter
import math
import re
import numpy as np
from .corpus import WORD_RE, sentence_spans, prose_markup

FUNCTION_WORDS = 'a an the and but or so if because while although of in on at by for from to with without about as is are was were be been have has had do does did can could would should will may might it this that these those'.split()
PUNCTUATION = {'comma': ',', 'period': '.', 'semicolon': ';', 'colon': ':', 'em_dash': '—', 'hyphen': '-', 'question': '?', 'exclamation': '!', 'double_quote': '"'}


def extract_features(text, raw_markdown=None):
    words = [w.lower() for w in WORD_RE.findall(text)]
    n = max(len(words), 1)
    counts = Counter(words)
    lengths = np.array([len(w) for w in words] or [0], dtype=float)
    sentences = sentence_spans(text)
    sl = np.array([len(WORD_RE.findall(s['text'])) for s in sentences] or [0], dtype=float)
    paragraphs = [p for p in re.split(r'\n\s*\n', text) if p.strip()]
    pl = np.array([len(WORD_RE.findall(p)) for p in paragraphs] or [0], dtype=float)
    rate = lambda ws: 1000 * sum(counts[w] for w in ws) / n
    f = {
        'sentence_length_mean': float(sl.mean()),
        'sentence_length_median': float(np.median(sl)),
        'sentence_length_std': float(sl.std()),
        'sentence_length_skew': float(np.mean(((sl-sl.mean()) / max(sl.std(), 1)) ** 3)),
        'paragraph_length_mean': float(pl.mean()),
        'paragraph_length_median': float(np.median(pl)),
        'paragraph_length_std': float(pl.std()),
        'sentences_per_paragraph': len(sentences) / max(len(paragraphs), 1),
        'word_length_mean': float(lengths.mean()),
        'word_length_std': float(lengths.std()),
        'type_token_ratio': len(counts) / n,
        'root_type_token_ratio': len(counts) / math.sqrt(n),
        'hapax_rate': sum(v == 1 for v in counts.values()) / n,
        'short_word_rate': float(np.mean(lengths <= 3)),
        'long_word_rate': float(np.mean(lengths >= 8)),
        'lexical_density_proxy': 1 - sum(counts[w] for w in FUNCTION_WORDS) / n,
        'contraction_rate': 1000 * sum("'" in w or '’' in w for w in words) / n,
        'first_person_singular_rate': rate(['i','me','my','mine','myself']),
        'first_person_plural_rate': rate(['we','us','our','ours','ourselves']),
        'second_person_rate': rate(['you','your','yours','yourself']),
        'third_person_rate': rate(['he','she','they','him','her','them','their']),
        'parenthetical_rate': 1000 * len(re.findall(r'\([^)]*\)', text)) / n,
        'question_sentence_rate': sum(s['text'].rstrip('"\'”’)').endswith('?') for s in sentences) / max(len(sentences), 1),
        'sentence_initial_conjunction_rate': sum(bool(re.match(r'(and|but|so|or)\b', s['text'], re.I)) for s in sentences) / max(len(sentences), 1),
        'one_sentence_paragraph_rate': sum(len(sentence_spans(p)) == 1 for p in paragraphs) / max(len(paragraphs), 1),
        'transition_rate': rate(['however','therefore','anyway','instead','meanwhile','finally','furthermore','nonetheless']),
        'hedge_rate': rate(['perhaps','maybe','probably','seems','possibly','apparently']),
        'intensifier_rate': rate(['very','really','extremely','quite','absolutely']),
        'subordinate_marker_rate': rate(['because','although','while','unless','since','whereas']),
        'passive_voice_proxy': 1000 * len(re.findall(r'\b(?:is|are|was|were|been|be)\s+\w+ed\b', text, re.I)) / n,
        'capitalized_word_rate': 1000 * len(re.findall(r'\b[A-Z][a-z]+\b', text)) / n,
        'uppercase_word_rate': 1000 * len(re.findall(r'\b[A-Z]{2,}\b', text)) / n,
    }
    structural = prose_markup(raw_markdown if raw_markdown is not None else text)
    f['heading_rate'] = 1000 * len(re.findall(r'(?m)^\s{0,3}#{1,6}\s+', structural)) / n
    f['list_rate'] = 1000 * len(re.findall(r'(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)', structural)) / n
    f['quote_paragraph_rate'] = 1000 * len(re.findall(r'(?m)^\s*>', structural)) / n
    f.update({f'function_{w}_rate': rate([w]) for w in FUNCTION_WORDS})
    f.update({f'{name}_rate': 1000 * text.count(symbol) / n for name, symbol in PUNCTUATION.items()})
    for left, right in [(1,3),(4,6),(7,9),(10,1000)]:
        f[f'word_length_{left}_{right}_fraction'] = float(np.mean((lengths >= left) & (lengths <= right)))
    return f


def feature_distribution(rows):
    keys = list(rows[0])
    matrix = np.array([[row[k] for k in keys] for row in rows])
    median = np.median(matrix, axis=0)
    std = matrix.std(axis=0)
    mad = 1.4826 * np.median(abs(matrix - median), axis=0)
    # A zero-MAD distribution is common with six posts. Avoid infinite deviations.
    floor = np.maximum(abs(median) * .1, .01)
    scale = np.maximum(np.maximum(mad, std * .25), floor)
    return keys, matrix, median, std, scale


def deviations(candidate, rows):
    keys, matrix, median, std, scale = feature_distribution(rows)
    result = []
    for i, key in enumerate(keys):
        value = candidate[key]
        z = float((value - median[i]) / scale[i])
        name = key.replace('function_', 'Function word: ').replace('_', ' ')
        result.append({'feature': key, 'label': name.capitalize(), 'candidate_value': float(value),
                       'historical_mean': float(matrix[:,i].mean()), 'historical_median': float(median[i]),
                       'historical_std': float(std[i]), 'robust_z': z,
                       'historical_percentile': float(100 * (np.sum(matrix[:,i] < value) + .5 * np.sum(matrix[:,i] == value)) / len(rows)),
                       'variable_in_history': bool(std[i] > 0),
                       'description': f'{name.capitalize()}: candidate {value:.3g}; historical median {median[i]:.3g}; ' + ('within the usual range.' if abs(z) < 1 else ('higher than usual.' if z > 0 else 'lower than usual.'))})
    return result


def stylometry_similarity(candidate, rows):
    d = deviations(candidate, rows)
    return float(np.exp(-np.mean([min(abs(r['robust_z']), 8) for r in d]) / 2))


def normalize_similarity(value, historical):
    values = np.asarray(historical, dtype=float)
    if not len(values):
        return float(np.clip(value, 0, 1))
    median = float(np.median(values))
    mad = float(1.4826 * np.median(abs(values - median)))
    scale = max(mad, float(values.std()) * .25, .05)
    z = float(np.clip((value - median) / scale, -30, 30))
    return float(1 / (1 + np.exp(-z)))


def evidence_strength(words, components):
    level = 0 if words < 150 else 1 if words < 500 else 2
    if max(components) - min(components) >= .65:
        level = max(0, level - 1)
    return ['LOW', 'MEDIUM', 'HIGH'][level]
