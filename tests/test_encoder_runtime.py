"""CPU execution avoids the macOS native worker-thread crash path."""
import sys
import pytest


@pytest.mark.skipif(sys.platform != 'darwin', reason='macOS CPU runtime safeguard')
def test_given_macos_cpu_inference_when_prepared_then_execution_uses_one_worker():
    # Given native libraries share a process with the authorship encoder.
    from style_fingerprint.embeddings import configure_inference_threads
    import torch
    # When CPU inference is prepared.
    configure_inference_threads('cpu')
    # Then encoder work avoids the crashing OpenMP worker-team path.
    assert torch.get_num_threads() == 1
