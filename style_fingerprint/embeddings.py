"""Pinned LUAR model boundary, passage cache keys, and symmetric MaxSim."""
import hashlib
import json
import os
import sys
from pathlib import Path
import numpy as np
from .config import ENCODING_VERSION, PREPROCESSING_VERSION


def cache_key(text, config):
    identity = [text, config.model_id, config.model_revision, ENCODING_VERSION, PREPROCESSING_VERSION]
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def cosine_matrix(a, b):
    a, b = np.asarray(a), np.asarray(b)
    a = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-12)
    b = b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-12)
    return np.clip(a @ b.T, -1, 1)


def symmetric_maxsim(a, b):
    sim = cosine_matrix(a, b)
    return float((sim.max(axis=1).mean() + sim.max(axis=0).mean()) / 2)


def configure_inference_threads(device):
    """Avoid macOS OpenMP worker crashes when encoder and challenger share a process."""
    if device == 'cpu' and sys.platform == 'darwin':
        import torch
        torch.set_num_threads(1)


class AuthorshipEncoder:
    def __init__(self, config):
        self.config = config
        self.model = None

    def _load(self):
        try:
            import torch
            os.environ.setdefault('HF_MODULES_CACHE', str(Path(self.config.model_cache).resolve() / 'modules'))
            from transformers import AutoModel, AutoTokenizer
            from huggingface_hub import snapshot_download
            torch.manual_seed(self.config.seed)
            device = self.config.device
            if device == 'auto':
                device = 'cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'
            configure_inference_threads(device)
            snapshot = snapshot_download(self.config.model_id, revision=self.config.model_revision,
                                         cache_dir=self.config.model_cache, local_files_only=self.config.local_files_only)
            self.model = AutoModel.from_pretrained(snapshot, trust_remote_code=True, local_files_only=True).to(device).eval()
            self.tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, fix_mistral_regex=False)
            self.device = device
        except Exception as exc:
            raise RuntimeError(f'Cannot load authorship model {self.config.model_id}@{self.config.model_revision}: {exc}. Install inference dependencies and download the pinned checkpoint; no substitute model is used.') from exc

    def encode(self, texts):
        if not texts:
            return np.empty((0, 512), dtype=np.float32)
        if self.model is None:
            self._load()
        import torch
        rows = []
        with torch.inference_mode():
            for start in range(0, len(texts), 4):
                batch = texts[start:start+4]
                if any(len(self.tokenizer.encode(t)) > 4096 for t in batch):
                    raise ValueError('A passage exceeds 4096 model tokens; shorten the paragraph rather than silently truncate it.')
                # Singleton episodes make each persisted passage independent of batch/reference context.
                vectors = self.model.encode([[t] for t in batch], self.tokenizer, output_type='multi',
                                            batch_size=4, max_length=4096, device=self.device)
                rows.append(vectors[:,0,:].float().cpu().numpy())
        result = np.concatenate(rows).astype(np.float32)
        if not np.isfinite(result).all() or np.any(np.linalg.norm(result, axis=1) == 0):
            raise RuntimeError('Authorship model returned invalid embeddings')
        return result
