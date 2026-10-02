import pytest


@pytest.mark.integration
def test_given_real_encoder_when_built_loaded_and_scored_then_pipeline_runs(tmp_path):
    from style_fingerprint import StyleFingerprint
    from style_fingerprint.config import Config
    fp = StyleFingerprint.build('blog_posts', tmp_path / 'real', config=Config(device='cpu', local_files_only=True))
    loaded = StyleFingerprint.load(tmp_path / 'real')
    text = open('tests/fixtures/candidate.txt').read()
    result = loaded.score(text, explain=False)
    assert 0 <= result.score <= 100
    assert result.nearest_reference_passages
    assert fp.embeddings.shape[1] == 512
