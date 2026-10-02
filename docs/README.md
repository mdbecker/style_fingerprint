# Documentation

[Current specification](specification.md) is authoritative; [root instructions](../AGENTS.md) define tests-first development, documentation upkeep, privacy, and output policy.

- [Implementation](implementation.md): algorithms, score math, persistence, and failure behavior.
- [Corpus handling](corpus.md): pooled positive sources, cleaning, provenance, and local privacy.
- [Evaluation](evaluation.md): seeded mixed holdout, nested group validation, report generation, and limitations.
- [Negative collection and licensing](negative-corpus.md): curated sources, extraction, and reuse terms.
- [Negative inventory](negative-inventory.md) and [curated source inputs](negative_sources.json): maintained public attribution and collection provenance.
- [Development](development.md): concise verification and current limitations.
- [Historical specifications](historical-specifications.md): consolidated supplied PRD, proposal, and original addendum; superseded requirements are historical.
- [User guide](../README.md): installation and API/CLI usage.

Generated evidence, metrics, exact private split identities, privacy scans, and HTML model reports stay in ignored artifacts. No per-run transcripts or intermediate evaluations are maintained here. The explicit inventory and local links are checked by `scripts/check_docs.py` and pytest.
