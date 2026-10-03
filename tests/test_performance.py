"""Performance behavior without hardware latency assertions."""
from dataclasses import replace
from types import SimpleNamespace
import pytest
from style_fingerprint.config import Config
from style_fingerprint import embeddings


def test_device_selection_and_explicit_failure():
    torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False), backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: True)))
    assert embeddings.resolve_device('auto', torch) == 'mps'
    torch.backends.mps.is_available = lambda: False
    with pytest.raises(RuntimeError, match='MPS was requested'):
        embeddings.resolve_device('mps', torch)


def test_precision_cache_identity():
    config = Config()
    assert embeddings.cache_key('invented prose', config) == embeddings.cache_key('invented prose', replace(config, device='mps'))
    assert embeddings.cache_key('invented prose', config) != embeddings.cache_key('invented prose', replace(config, encoder_dtype='float16'))


def test_fast_has_no_deletions_and_deep_is_bounded(fingerprint):
    text = fingerprint.documents[0].clean_text
    fast = fingerprint.score(text, analysis_mode='fast')
    deep = fingerprint.score(text, analysis_mode='deep')
    assert fast.score == deep.score
    assert fast.diagnostics['sentence_deletions_evaluated'] == 0
    assert fast.anomalous_passages
    assert 0 < deep.diagnostics['sentence_deletions_evaluated'] <= 20


def test_api_defaults_fast_and_reports_duration(fingerprint):
    from fastapi.testclient import TestClient
    from style_fingerprint.web import create_app
    with TestClient(create_app(fingerprint=fingerprint)) as client:
        response = client.post('/api/analyze', json={'text': fingerprint.documents[0].clean_text}).json()
        assert response['analysis_mode'] == 'fast'
        assert response['timing_ms'] >= 0
        assert all(row['delta'] is None for row in response['segments'])
        assert client.post('/api/analyze', json={'text': 'Some invented prose.', 'mode': 'invalid'}).status_code == 422


def test_precision_gate_requires_every_threshold():
    metrics = dict(decision_agreement=1., mean_score_drift=.5, max_score_drift=1.5, auroc_decline=.005, brier_degradation=.005, latency_improvement=.2)
    assert embeddings.accept_float16(metrics)
    for key in metrics:
        bad = dict(metrics)
        bad[key] += -.01 if key in {'decision_agreement', 'latency_improvement'} else .01
        assert not embeddings.accept_float16(bad)


def test_gpu_batches_restore_order_and_retry_once():
    import numpy as np
    import torch
    from style_fingerprint.embeddings import AuthorshipEncoder
    class Model:
        def __init__(self): self.calls = 0
        def encode(self, episodes, tokenizer, **kwargs):
            assert torch.is_inference_mode_enabled()
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError('MPS out of memory')
            return torch.tensor([[[len(e[0]), 1.]] for e in episodes])
    encoder = AuthorshipEncoder(Config())
    encoder.model = Model()
    encoder.device = 'mps'
    encoder.batch_size = 16
    encoder.tokenizer = SimpleNamespace(encode=lambda t: t.split())
    texts = ['invented ' * i for i in range(20, 0, -1)]
    # Only the external hardware encoder/cache boundary is substituted.
    from unittest.mock import patch
    with patch.object(torch.mps, 'empty_cache'):
        result = encoder.encode(texts)
    assert np.array_equal(result[:, 0], [len(t) for t in texts])
    assert encoder.batch_size == 8


@pytest.mark.integration
def test_real_mps_warmup_and_finite_embeddings():
    import torch
    import numpy as np
    if not torch.backends.mps.is_available():
        pytest.skip('Native MPS unavailable')
    encoder = embeddings.AuthorshipEncoder(Config(device='mps', local_files_only=True))
    encoder.prepare()
    result = encoder.encode(['This invented example exercises the real authorship encoder.'])
    assert encoder.device == 'mps'
    assert encoder.batch_size == 16
    assert result.shape == (1, 512)
    assert np.isfinite(result).all()


def test_cpu_artifact_server_uses_runtime_mps_and_warms_once(fingerprint, tmp_path, monkeypatch, capsys):
    from fastapi.testclient import TestClient
    from style_fingerprint.web import create_app
    loaded = []
    def load_encoder(self):
        loaded.append(self.config.device)
        self.model = object()
        self.device = 'mps'
        self.dtype = self.config.encoder_dtype
        self.batch_size = 16
    # Substitute only the external encoder loading boundary; real artifact load remains.
    monkeypatch.setattr(embeddings.AuthorshipEncoder, '_load', load_encoder)
    with TestClient(create_app(tmp_path / 'artifacts', device='auto')) as client:
        assert client.get('/api/health').json() == {'status':'ok','model_loaded':True,'device':'mps','dtype':'float32','embedding_batch_size':16}
        client.app.state.fingerprint.encoder.prepare()
        assert loaded == ['auto']
        assert client.post('/api/analyze',json={'text':'This invented prose stays private.'}).status_code == 200
    assert capsys.readouterr().out.count('LUAR encoder ready:') == 1


def test_gpu_operation_failure_surfaces_at_startup(fingerprint, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from style_fingerprint.web import create_app
    def unsupported(self):
        raise RuntimeError('Unsupported MPS operation')
    monkeypatch.setattr(embeddings.AuthorshipEncoder, '_load', unsupported)
    with pytest.raises(RuntimeError, match='Unsupported MPS operation'):
        with TestClient(create_app(tmp_path / 'artifacts')):
            pass


def test_legacy_fp32_cache_survives_device_only_rebuild(fingerprint, corpus, encoder, tmp_path):
    import hashlib, json
    import pandas as pd
    from style_fingerprint.model import StyleFingerprint
    bank = tmp_path / 'artifacts'
    manifest = json.loads((bank / 'manifest.json').read_text())
    manifest['configuration'].pop('encoder_dtype')
    frame = pd.read_parquet(bank / 'passages.parquet')
    frame['embedding_key'] = [embeddings.cache_key(text, fingerprint.config, legacy=True) for text in frame['text']]
    frame.to_parquet(bank / 'passages.parquet', index=False)
    manifest['artifact_hashes']['passages.parquet'] = hashlib.sha256((bank / 'passages.parquet').read_bytes()).hexdigest()
    (bank / 'manifest.json').write_text(json.dumps(manifest))
    assert StyleFingerprint.load(bank).config.encoder_dtype == 'float32'
    encoder.clear()
    StyleFingerprint.build(corpus, bank, holdout_fraction=0, config=replace(fingerprint.config, device='mps'))
    assert not encoder
