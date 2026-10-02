import numpy as np
import pytest


def test_given_prose_when_measured_then_features_are_finite_interpretable_and_structural():
    from style_fingerprint.features import extract_features
    f = extract_features('I think this is useful. We agree!\n\nWhy not try (carefully)?', '# Heading\n- Item')
    assert 50 <= len(f) <= 100
    assert all(np.isfinite(v) for v in f.values())
    assert f['sentence_length_mean'] > 0
    assert f['first_person_singular_rate'] > 0
    assert f['heading_rate'] > 0 and f['list_rate'] > 0
    assert f['parenthetical_rate'] > 0


def test_given_multivectors_when_compared_then_symmetric_maxsim_retains_passage_information():
    from style_fingerprint.embeddings import symmetric_maxsim
    a = np.eye(2)
    b = np.array([[1., 0.]])
    assert symmetric_maxsim(a, b) == pytest.approx(.75)
    assert symmetric_maxsim(b, a) == pytest.approx(.75)


def test_given_historical_distribution_when_normalized_then_monotonic_bounded_and_not_probability():
    from style_fingerprint.features import normalize_similarity
    values = [.4, .5, .6, .7, .8]
    mapped = [normalize_similarity(v, values) for v in [-1, .4, .6, .8, 1]]
    assert mapped == sorted(mapped)
    assert 0 <= min(mapped) <= max(mapped) <= 1
    assert mapped[2] == pytest.approx(.5)


@pytest.mark.parametrize('words,components,expected', [(149,[.5,.5,.5],'LOW'),(150,[.5,.5,.5],'MEDIUM'),(499,[.5,.5,.5],'MEDIUM'),(500,[.5,.5,.5],'HIGH'),(500,[.05,.95,.9],'MEDIUM'),(150,[.05,.95,.9],'LOW')])
def test_given_length_and_component_agreement_when_evidence_reported_then_fixed_rules_apply(words, components, expected):
    from style_fingerprint.features import evidence_strength
    assert evidence_strength(words, components) == expected


def test_given_changed_model_identity_when_cache_keyed_then_keys_change():
    from style_fingerprint.embeddings import cache_key
    from style_fingerprint.config import Config
    base = cache_key('passage', Config())
    assert base != cache_key('changed', Config())
    assert base != cache_key('passage', Config(model_revision='new'))
    assert base != cache_key('passage', Config(model_id='different/model'))


def test_given_unavailable_encoder_when_loaded_then_clear_failure_without_substitute(monkeypatch):
    from style_fingerprint.embeddings import AuthorshipEncoder
    from style_fingerprint.config import Config
    import transformers
    def unavailable(*args, **kwargs):
        raise OSError('missing weights')
    monkeypatch.setattr(transformers.AutoModel, 'from_pretrained', unavailable)
    with pytest.raises(RuntimeError, match='Cannot load authorship model'):
        AuthorshipEncoder(Config(local_files_only=True)).encode(['A real passage.'])


def test_given_offline_snapshot_when_model_loaded_then_tokenizer_uses_local_files(monkeypatch, tmp_path):
    from style_fingerprint.embeddings import AuthorshipEncoder
    from style_fingerprint.config import Config
    import huggingface_hub
    import transformers
    seen = []
    monkeypatch.setattr(huggingface_hub, 'snapshot_download', lambda *a, **kw: str(tmp_path))
    class Weights:
        def to(self, device): return self
        def eval(self): return self
    monkeypatch.setattr(transformers.AutoModel, 'from_pretrained', lambda path, **kw: (seen.append(path) or Weights()))
    monkeypatch.setattr(transformers.AutoTokenizer, 'from_pretrained', lambda path, **kw: (seen.append(path) or object()))
    AuthorshipEncoder(Config(device='cpu', local_files_only=True))._load()
    assert seen == [str(tmp_path), str(tmp_path)]


def test_given_qwen_tokenizer_when_loaded_then_mistral_regex_is_not_applied(monkeypatch, tmp_path):
    from style_fingerprint.embeddings import AuthorshipEncoder
    from style_fingerprint.config import Config
    import huggingface_hub
    import transformers
    monkeypatch.setattr(huggingface_hub, 'snapshot_download', lambda *a, **kw: str(tmp_path))
    class Weights:
        def to(self, device): return self
        def eval(self): return self
    options = {}
    monkeypatch.setattr(transformers.AutoModel, 'from_pretrained', lambda *a, **kw: Weights())
    def tokenizer(*args, **kwargs):
        options.update(kwargs)
        return object()
    monkeypatch.setattr(transformers.AutoTokenizer, 'from_pretrained', tokenizer)
    AuthorshipEncoder(Config(device='cpu'))._load()
    assert options.get('fix_mistral_regex') is False
