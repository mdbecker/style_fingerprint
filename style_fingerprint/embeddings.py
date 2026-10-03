"""Pinned LUAR model boundary, passage cache keys, and symmetric MaxSim."""
import hashlib
import json
import os
import sys
from pathlib import Path
import numpy as np
from .config import ENCODING_VERSION, PREPROCESSING_VERSION


def cache_key(text, config, *, legacy=False):
    identity = [text, config.model_id, config.model_revision, ENCODING_VERSION, PREPROCESSING_VERSION]
    if not legacy:
        identity.append(config.encoder_dtype)
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


def resolve_device(requested, torch):
    available = {'cuda': torch.cuda.is_available(), 'mps': torch.backends.mps.is_available(), 'cpu': True}
    if requested == 'auto':
        return next(d for d in ('cuda', 'mps', 'cpu') if available[d])
    if requested not in available:
        raise ValueError('Device must be auto, cpu, cuda, or mps')
    if not available[requested]:
        raise RuntimeError(f'{requested.upper()} was requested but is unavailable in this Python/PyTorch environment.')
    return requested


def accept_float16(metrics):
    return (metrics['decision_agreement'] == 1 and metrics['mean_score_drift'] <= .5
            and metrics['max_score_drift'] <= 1.5 and metrics['auroc_decline'] <= .005
            and metrics['brier_degradation'] <= .005 and metrics['latency_improvement'] >= .2)


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
            device = resolve_device(self.config.device, torch)
            configure_inference_threads(device)
            snapshot = snapshot_download(self.config.model_id, revision=self.config.model_revision,
                                         cache_dir=self.config.model_cache, local_files_only=self.config.local_files_only)
            self.model = AutoModel.from_pretrained(snapshot, trust_remote_code=True, local_files_only=True).to(device=device, dtype=getattr(torch, self.config.encoder_dtype)).eval()
            self.tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True, fix_mistral_regex=False)
            self.device = device
            self.dtype = self.config.encoder_dtype
            self.batch_size = self.config.embedding_batch_size or (4 if device == 'cpu' else 16)
        except Exception as exc:
            raise RuntimeError(f'Cannot load authorship model {self.config.model_id}@{self.config.model_revision}: {exc}. Install inference dependencies and download the pinned checkpoint; no substitute model is used.') from exc

    def encode(self, texts):
        if not texts:
            return np.empty((0, 512), dtype=np.float32)
        if self.model is None:
            self._load()
        import torch
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        rows = []
        start = 0
        retried = False
        with torch.inference_mode():
            while start < len(order):
                batch = [texts[i] for i in order[start:start+self.batch_size]]
                if any(len(self.tokenizer.encode(t)) > 4096 for t in batch):
                    raise ValueError('A passage exceeds 4096 model tokens; shorten the paragraph rather than silently truncate it.')
                try:
                    vectors = self.model.encode([[t] for t in batch], self.tokenizer, output_type='multi',
                                                batch_size=self.batch_size, max_length=4096, device=self.device)
                    rows.append(vectors[:,0,:].float().cpu().numpy())
                    start += len(batch)
                except RuntimeError as exc:
                    if self.device != 'cpu' and 'out of memory' in str(exc).lower() and not retried and self.batch_size == 16:
                        self.batch_size = 8
                        retried = True
                        getattr(torch, self.device).empty_cache()
                        continue
                    raise
        result = np.concatenate(rows).astype(np.float32)[np.argsort(order)]
        if not np.isfinite(result).all() or np.any(np.linalg.norm(result, axis=1) == 0):
            raise RuntimeError('Authorship model returned invalid embeddings')
        return result

    def prepare(self):
        """Load once and warm with application-owned prose before readiness."""
        if getattr(self, '_ready', False):
            return
        if self.model is None:
            self._load()
        if self.device != 'cpu':
            self.encode(['This is a fixed warm up sample for the writing style encoder.'])
        self._ready = True
        print(f'LUAR encoder ready: device={self.device} dtype={self.dtype} batch_size={self.batch_size}')
