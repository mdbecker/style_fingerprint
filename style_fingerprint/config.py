"""Deliberately small configuration; statistical defaults are fixed for the MVP."""
from dataclasses import dataclass

VERSION = '0.1.0'
FEATURE_SCHEMA_VERSION = '2'
PREPROCESSING_VERSION = '2'
ENCODING_VERSION = 'singleton-episode-full-passage-v1'
WEIGHTS = {'authorship_embedding': .60, 'stylometry': .25, 'char_ngram': .15}


@dataclass(frozen=True)
class Config:
    model_id: str = 'rrivera1849/LUAR-MUD-MV-Qwen'
    model_revision: str = '9dea156891cbd054f8254ffea1690a9aafa0a2e2'
    seed: int = 42
    device: str = 'auto'
    model_cache: str = '.cache/huggingface'
    local_files_only: bool = False

    def __post_init__(self):
        if self.device not in {'auto', 'cpu', 'cuda', 'mps'}:
            raise ValueError('Device must be auto, cpu, cuda, or mps')
        if not self.model_revision:
            raise ValueError('An explicit model revision is required')
