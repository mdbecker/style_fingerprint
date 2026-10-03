"""Self-editor behaviors use the production fingerprint; only encoder is replaced."""
from pathlib import Path
import pytest


def test_plain_text_keeps_exact_original_offsets(fingerprint):
    text = '  📝 **A repeated sentence is here!**\r\n\r\n' + ('BUY NOW! WIN BIG! ACT FAST! ' * 60)
    result = fingerprint.score(text, input_format='plain')
    for row in result.anomalous_passages:
        assert text[row['start_char']:row['end_char']] == row['text']
    for row in result.anomalous_sentences:
        assert text[row['start_char']:row['end_char']] == row['sentence']
    assert result.diagnostics['input_format'] == 'plain'


@pytest.fixture
def client(fingerprint):
    from fastapi.testclient import TestClient
    from style_fingerprint.web import create_app
    with TestClient(create_app(fingerprint=fingerprint)) as client:
        yield client


def test_analysis_returns_existing_scores_and_exact_nonoverlapping_ranges(client, fingerprint):
    text = '📝\r\n  ' + fingerprint.documents[0].clean_text + '\r\n\r\n' + ('BUY NOW! WIN BIG! ACT FAST! ' * 45)
    expected = fingerprint.score(text, input_format='plain')
    response = client.post('/api/analyze', json={'text': text})
    assert response.status_code == 200
    data = response.json()
    assert data['score'] == expected.score
    assert data['decision'] == expected.decision
    assert data['evidence_strength'] == expected.evidence_strength
    assert data['word_count'] == expected.word_count
    assert data['component_scores'] == expected.component_scores
    assert data['thresholds'] == {'match': expected.match_threshold, 'mismatch': expected.mismatch_threshold}
    assert 0 < len(data['segments']) <= 10
    end = 0
    for row in sorted(data['segments'], key=lambda x: x['start']):
        assert row['start'] >= end
        end = row['end']
        assert text[row['start']:end] == row['text']
        assert row['severity'] in {'low', 'medium', 'high'}
        assert row['type'] == 'sentence'
        assert row['reasons']
    assert len(data['strongest_matches']) <= 3
    assert len(data['largest_mismatches']) <= 3
    assert 'nearest_reference_passages' not in data
    assert 'source_file' not in response.text


@pytest.mark.parametrize('payload,status,code', [
    ({'text': ''}, 422, 'INVALID_TEXT'), ({'text': 'one two'}, 422, 'TEXT_TOO_SHORT'),
    ({'text': 'a' * 50001}, 413, 'TEXT_TOO_LONG'), ({'text': 123}, 422, 'INVALID_TEXT'),
    ({}, 422, 'INVALID_TEXT'), (['wrong'], 422, 'INVALID_TEXT'),
])
def test_validation_has_consistent_safe_errors(client, payload, status, code):
    response = client.post('/api/analyze', json=payload)
    assert response.status_code == status
    assert response.json()['error'] == code
    assert set(response.json()) == {'error', 'message'}


def test_short_prose_obeys_existing_low_evidence_rule(client):
    response = client.post('/api/analyze', json={'text': 'This is a brief invented sentence.'})
    assert response.status_code == 200
    assert response.json()['evidence_strength'] == 'LOW'


def test_same_fingerprint_reused_and_private_prose_not_written_or_logged(client, fingerprint, caplog, tmp_path):
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    prose = 'An invented confidential canary phrase stays only in memory.'
    for _ in range(2):
        assert client.post('/api/analyze', json={'text': prose}).status_code == 200
    assert client.app.state.fingerprint is fingerprint
    assert before == {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert prose not in caplog.text
    assert client.get('/api/health').json() == {'status': 'ok', 'model_loaded': True}


def test_page_is_self_contained_and_never_cached(client):
    response = client.get('/')
    assert response.status_code == 200
    assert 'Analyze style' in response.text
    assert '<textarea' in response.text
    assert 'src="http' not in response.text
    assert 'no-store' in response.headers['cache-control']


def test_unavailable_model_is_clear_without_tracebacks():
    from fastapi.testclient import TestClient
    from style_fingerprint.web import create_app
    with TestClient(create_app(artifact_dir='/does-not-exist')) as client:
        assert client.get('/api/health').json() == {'status': 'unavailable', 'model_loaded': False}
        response = client.post('/api/analyze', json={'text': 'Some valid invented prose.'})
        assert response.status_code == 503
        assert response.json()['error'] == 'MODEL_UNAVAILABLE'
        assert '/does-not-exist' not in response.text


def test_serve_cli_defaults_are_local():
    from style_fingerprint.cli import _parser
    args = _parser().parse_args(['serve'])
    assert args.host == '127.0.0.1'
    assert args.port == 8000
    assert args.artifacts == 'artifacts'


def test_malformed_and_oversized_request_bodies_are_safe(client):
    response = client.post('/api/analyze', content=b'{bad-json', headers={'Content-Type': 'application/json'})
    assert response.status_code == 422
    assert response.json()['error'] == 'INVALID_TEXT'
    response = client.post('/api/analyze', content=b'x' * 650001)
    assert response.status_code == 413
    assert response.json()['error'] == 'TEXT_TOO_LONG'


def test_request_releases_derived_candidate_cache(client, fingerprint):
    before = set(fingerprint._embedding_cache)
    assert client.post('/api/analyze', json={'text': 'A completely new invented draft uses unusual words.'}).status_code == 200
    assert set(fingerprint._embedding_cache) == before


def test_encoder_failure_is_safe_and_next_request_recovers(client, fingerprint, monkeypatch):
    from style_fingerprint.embeddings import AuthorshipEncoder
    original = AuthorshipEncoder.encode
    def fail(self, texts):
        raise RuntimeError('Sensitive invented phrase inside encoder failure')
    monkeypatch.setattr(AuthorshipEncoder, 'encode', fail)
    response = client.post('/api/analyze', json={'text': 'A fresh invented candidate reaches the external encoder.'})
    assert response.status_code == 500
    assert response.json()['error'] == 'ANALYSIS_FAILED'
    assert 'Sensitive' not in response.text
    monkeypatch.setattr(AuthorshipEncoder, 'encode', original)
    assert client.post('/api/analyze', json={'text': 'A fresh invented candidate reaches the external encoder.'}).status_code == 200
