"""Small same-origin, read-only interface over production scoring/explanation."""
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
import json
from time import perf_counter
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from .corpus import sentence_spans, word_count
from .model import StyleFingerprint

MAX_CHARACTERS = 50_000
# Allows even fully JSON-escaped Unicode, while bounding the body before parsing.
MAX_BODY_BYTES = 650_000
PAGE = Path(__file__).with_name('web') / 'index.html'


def error(code, message, status):
    return JSONResponse({'error': code, 'message': message}, status_code=status)


def present(result, text):
    """Adapt existing deletion/passage evidence; never expose private analogues."""
    sentences = sentence_spans(text)
    by_start = {row['start_char']: row for row in result.anomalous_sentences}
    candidates = []
    for sentence in sentences:
        start, end = sentence['start_char'], sentence['end_char']
        passage = next((p for p in result.anomalous_passages
                        if p['start_char'] <= start < p['end_char']), None)
        deletion = by_start.get(start)
        # Short documents have no deletion analysis: only highlight a passage
        # when its existing score is actually lower than the whole document.
        if deletion is None and (passage is None or passage['score'] is None
                                 or passage['score'] >= result.score):
            continue
        delta = deletion['delta'] if deletion else None
        gap = delta if delta is not None else result.score - passage['score']
        reasons = [d['description'] for d in (passage or {}).get('largest_mismatches', [])[:2]]
        if delta is not None:
            reasons.insert(0, f'Removing this sentence raises document compatibility by {delta:.1f} points. This measures sensitivity, not causation.')
        else:
            reasons.insert(0, 'This sentence lies in a passage with lower compatibility than the draft overall; the score is for that passage.')
        candidates.append({'start': start, 'end': end, 'text': text[start:end],
                           'type': 'sentence', 'compatibility': passage['score'] if passage else None,
                           'compatibility_scope': 'passage', 'delta': delta,
                           'severity': 'high' if gap >= 5 else 'medium' if gap >= 2 else 'low',
                           'reasons': reasons, '_rank': gap})
    ranked = sorted(candidates, key=lambda row: (-row['_rank'], row['start']))[:10]
    for row in ranked:
        row.pop('_rank')
    return {'score': result.score, 'decision': result.decision,
            'evidence_strength': result.evidence_strength, 'word_count': result.word_count,
            'thresholds': {'match': result.match_threshold, 'mismatch': result.mismatch_threshold},
            'component_scores': result.component_scores, 'segments': sorted(ranked, key=lambda row: row['start']),
            'strongest_matches': result.strongest_matches[:3],
            'largest_mismatches': ranked[:3],
            'warnings': ([f'{result.word_count} words gives limited evidence. Longer drafts provide a more reliable comparison.']
                         if result.word_count < 150 else []),
            'offset_unit': 'unicode_code_points'}


def create_app(artifact_dir='artifacts', *, fingerprint=None, device='auto'):
    lock = Lock()

    @asynccontextmanager
    async def lifespan(app):
        app.state.fingerprint = fingerprint
        if fingerprint is None:
            try:
                fp = await run_in_threadpool(StyleFingerprint.load, artifact_dir)
            except (ValueError, OSError):
                app.state.fingerprint = None
            else:
                # Encoder failures, including unsupported GPU operations, abort startup.
                fp.encoder.config = replace(fp.encoder.config, local_files_only=True, device=device)
                await run_in_threadpool(fp.encoder.prepare)
                app.state.fingerprint = fp
        yield
        app.state.fingerprint = None

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def protect_response(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.get('/')
    def page():
        return HTMLResponse(PAGE.read_text(encoding='utf-8'))

    @app.get('/api/health')
    def health():
        loaded = app.state.fingerprint is not None
        result = {'status': 'ok' if loaded else 'unavailable', 'model_loaded': loaded}
        if loaded:
            encoder = app.state.fingerprint.encoder
            result.update(device=getattr(encoder, 'device', 'cpu'), dtype=encoder.config.encoder_dtype,
                          embedding_batch_size=getattr(encoder, 'batch_size', 4))
        return result

    def analyze_text(text, mode):
        started = perf_counter()
        with lock:
            fp = app.state.fingerprint
            if fp is None:
                return error('MODEL_UNAVAILABLE', 'The local fingerprint is unavailable. Build it and ensure the pinned model is cached, then restart the server.', 503)
            original_cache = fp._embedding_cache.copy()
            try:
                result = fp.score(text, explain=True, input_format='plain', analysis_mode=mode)
                response = present(result, text)
                response.update(analysis_mode=mode, timing_ms=round((perf_counter()-started)*1000))
                return response
            except ValueError:
                return error('INVALID_TEXT', 'This text cannot be analyzed. Use ordinary prose and shorten unusually long paragraphs.', 422)
            except Exception:
                return error('ANALYSIS_FAILED', 'Style analysis failed. Try again or restart the local server.', 500)
            finally:
                # Do not retain even derived candidate vectors between requests.
                fp._embedding_cache = original_cache

    @app.post('/api/analyze')
    async def analyze(request: Request):
        body = bytearray()
        async for part in request.stream():
            body.extend(part)
            if len(body) > MAX_BODY_BYTES:
                return error('TEXT_TOO_LONG', 'Use no more than 50,000 characters.', 413)
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeError):
            return error('INVALID_TEXT', 'Submit a JSON object containing plain text.', 422)
        mode = payload.get('mode', 'fast') if isinstance(payload, dict) else 'fast'
        if not isinstance(mode, str) or mode not in {'fast', 'deep'}:
            return error('INVALID_MODE', 'Analysis mode must be fast or deep.', 422)
        text = payload.get('text') if isinstance(payload, dict) else None
        if not isinstance(text, str) or not text.strip():
            return error('INVALID_TEXT', 'Enter some writing before analyzing.', 422)
        if len(text) > MAX_CHARACTERS:
            return error('TEXT_TOO_LONG', 'Use no more than 50,000 characters.', 413)
        if word_count(text) < 3:
            return error('TEXT_TOO_SHORT', 'Enter at least three words before running style analysis.', 422)
        return await run_in_threadpool(analyze_text, text, mode)

    return app
