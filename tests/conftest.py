from pathlib import Path
import hashlib
import numpy as np
import pytest


@pytest.fixture
def encoder(monkeypatch):
    # The only replaced boundary is the external pretrained encoder.
    from style_fingerprint.embeddings import AuthorshipEncoder
    calls = []
    def encode(self, texts):
        calls.extend(texts)
        rows = []
        for text in texts:
            words = text.lower().split()
            row = np.ones(16) * 0.01
            for word in words:
                row[int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % 16] += 1
            row[0] += text.count('!') * 50
            rows.append(row / np.linalg.norm(row))
        return np.asarray(rows, dtype=np.float32)
    monkeypatch.setattr(AuthorshipEncoder, 'encode', encode)
    return calls


@pytest.fixture
def corpus(tmp_path):
    root = tmp_path / 'blog_posts'
    root.mkdir()
    for i in range(6):
        paragraph = (f"I think this experiment number {i} is interesting, and I would like to explain why. "
                     "We can look at the data together (which seems useful), but there is more to the story. "
                     "Anyway, the practical lesson is that careful comparisons help us understand the result. ") * 3
        (root / f'post-{i}.markdown').write_text('---\ntitle: Sample\n---\n# Experiment\n\n' + '\n\n'.join([paragraph] * 4))
    return root


@pytest.fixture
def fingerprint(corpus, encoder, tmp_path):
    from style_fingerprint import StyleFingerprint
    return StyleFingerprint.build(corpus, tmp_path / 'artifacts', holdout_fraction=0)
