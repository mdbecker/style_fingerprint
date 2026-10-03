"""Warm runtime comparison; all generated evidence stays local in artifacts."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import torch
from sklearn.metrics import roc_auc_score, brier_score_loss
from style_fingerprint.model import StyleFingerprint
from style_fingerprint.embeddings import AuthorshipEncoder, accept_float16
from style_fingerprint.corpus import chunk_text
from style_fingerprint.web import present


def timed(function, repeats):
    samples = []
    result = None
    for _ in range(repeats):
        started = perf_counter()
        result = function()
        samples.append((perf_counter()-started)*1000)
    return median(samples), result


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--artifacts', default='artifacts')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', default='artifacts/performance/benchmark.json')
    parser.add_argument('--precision-experiment', action='store_true')
    args = parser.parse_args()
    if args.repeats < 2:
        parser.error('Use at least two warm repetitions')
    output = Path(args.output)
    if 'artifacts' not in output.parts:
        raise ValueError('Benchmark output must remain under artifacts')
    output.parent.mkdir(parents=True, exist_ok=True)
    fp = StyleFingerprint.load(args.artifacts)
    original_cache = fp._embedding_cache.copy()
    report = {'cases': []}
    from style_fingerprint.corpus import word_count
    positives = [d for d in fp.documents if d.document_id in fp.manifest['historical_document_ids']]
    workloads = {n: min(positives, key=lambda d: abs(word_count(d.clean_text)-n)).clean_text
                 for n in (300, 1000, 2000)}
    runtimes = [('cpu', 'float32')]
    if torch.backends.mps.is_available():
        runtimes += [('mps', 'float32'), ('mps', 'float16')]
    encoders = {}
    for device, dtype in runtimes:
        encoder = AuthorshipEncoder(replace(fp.config, device=device, encoder_dtype=dtype, local_files_only=True))
        encoder.prepare()
        encoders[device, dtype] = encoder
        for words, text in workloads.items():
            passages = [p.text for p in chunk_text(text, 'benchmark')]
            encoder.encode(passages)  # excluded case warm-up, including CPU
            tokenize_ms, _ = timed(lambda: [encoder.tokenizer.encode(t) for t in passages], args.repeats)
            latency, _ = timed(lambda: encoder.encode(passages), args.repeats)
            row = {'device': device, 'dtype': dtype, 'words': words, 'actual_words': word_count(text), 'encoder_ms': latency, 'preflight_tokenization_ms': tokenize_ms}
            # Never score FP16 candidates against FP32 references.
            if dtype == fp.config.encoder_dtype:
                fp.encoder = encoder
                for mode in ('fast', 'deep'):
                    def analyze():
                        fp._embedding_cache = original_cache.copy()
                        return present(fp.score(text, input_format='plain', analysis_mode=mode), text)
                    analyze()
                    row[mode+'_ms'], _ = timed(analyze, args.repeats)
            report['cases'].append(row)
            output.write_text(json.dumps(report, indent=2, allow_nan=False))
            print(f'Completed warm case: device={device} dtype={dtype} words={words}', flush=True)
    if args.precision_experiment and ('mps', 'float16') in encoders:
        predictions = {}
        # Frozen examples/populations; no selection or retraining occurs.
        import pandas as pd
        frame = pd.read_parquet(Path(args.artifacts)/'evaluation_predictions.parquet')
        roots = list(dict.fromkeys(frame['root_document_id']))
        documents = {d.root_document_id: d for d in fp.documents}
        from style_fingerprint.corpus import Document
        for row in fp.manifest.get('holdout_documents', []):
            doc = Document(**row)
            documents[doc.root_document_id] = doc
        labels = frame.drop_duplicates('root_document_id').set_index('root_document_id')['label']
        if any(root not in documents for root in roots):
            raise ValueError('Frozen examples unavailable; cannot accept FP16')
        for dtype in ('float32', 'float16'):
            encoder = encoders['mps', dtype]
            vectors = encoder.encode([p.text for p in fp.passages])
            candidate = StyleFingerprint(fp.documents, fp.passages, vectors, replace(fp.config, encoder_dtype=dtype), fp.manifest, fp.evaluation, fp.verifier)
            candidate.encoder = encoder
            # Preserve fitted CPU vocabulary/statistics, refresh only reference vectors.
            reference = fp._reference(fp.manifest['historical_document_ids'])
            candidate._reference(fp.manifest['historical_document_ids'], vectorizer=reference['vectorizer'])
            predictions[dtype] = [candidate.score(documents[root].clean_text, explain=False) for root in roots]
        a,b = predictions['float32'],predictions['float16']
        sa,sb = np.array([r.score for r in a]), np.array([r.score for r in b])
        y = np.array([labels[root] for root in roots])
        medium = {row['dtype']:row['encoder_ms'] for row in report['cases'] if row['device']=='mps' and row['words']==1000}
        metrics = dict(decision_agreement=float(np.mean([x.decision==z.decision for x,z in zip(a,b)])), mean_score_drift=float(abs(sa-sb).mean()),max_score_drift=float(abs(sa-sb).max()),auroc_decline=float(roc_auc_score(y,sa)-roc_auc_score(y,sb)),brier_degradation=float(brier_score_loss(y,sb/100)-brier_score_loss(y,sa/100)),latency_improvement=1-medium['float16']/medium['float32'])
        report['precision_gate'] = {'metrics':metrics,'accepted':accept_float16(metrics), 'default_dtype':'float16' if accept_float16(metrics) else 'float32'}
    output.write_text(json.dumps(report,indent=2,allow_nan=False))
    print(f'Benchmark saved to {output}')


if __name__ == '__main__':
    main()
