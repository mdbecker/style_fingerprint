# Positive corpus handling

Blogs and configured private plain-text email sources form one positive class with equal document weights. Source labels support provenance and diagnostics; they do not create separate models or source-dependent weighting. The seeded [evaluation policy](evaluation.md) reserves the mixed-class holdout before fitting. Dataset totals and split sizes are generated from current inputs rather than copied into maintained docs.

## Discovery and rebuilds

Markdown input discovery accepts `.md`, `.markdown`, and `.mdown` recursively and case-insensitively. Configured email input discovery accepts `.txt` recursively. Preserve source originals rather than combining messages into artificial longer examples. Each document retains its identity, raw and cleaned text, metadata, and hashes privately in generated artifacts. Explicit missing or empty source directories fail clearly.

```sh
python -m style_fingerprint build --device cpu --offline
python -m style_fingerprint score new-email.txt --input-format email
python -m style_fingerprint explain new-email.txt --input-format email
python -m style_fingerprint evaluate --json
```

Scoring defaults to Markdown; choose `input_format='email'` for plain-text exports. Passage scoring and deletion explanations use the selected format. Loading evaluates the persisted snapshot; rebuild to adopt changed sources. Offline mode requires the cached pinned checkpoint. Unchanged passage/model/version combinations reuse expensive embeddings.

## Authorship and cleaning

Private examples are assumed to contain the user's authored prose. Source metadata preserves provenance; dates and conversations cannot be inferred reliably from filenames or timestamps. Plain-text exports may contain longer authored presentations as well as correspondence.

Email cleaning preserves greetings, authored closings, indentation, punctuation, contractions, underscores, and paragraph structure. It removes recognizable exported headers, quoted lines, reply/forwarded-message boundaries, signature separators, short trailing author/contact signatures, image placeholders, URLs, and email addresses. Early author credits in long documents do not discard their body. Cleaned prose supplies structural features, so stripped content does not reappear during measurement.

This conservative cleaner is not a complete mail parser or de-identification system. Review atypical signatures, inline quotations, boilerplate, source code, template content, and other people's contributions. Separate messages may belong to related conversations; no thread-disjoint or chronological guarantee is possible without that metadata.

## Training and local privacy

Every positive root contributes equal document weight, divided across its deterministic training views. Views retain root identity and are not independent documents. Known negative authors share equal total influence across their roots and views. Class-balanced sigmoid calibration gives each class equal total mass; source labels do not alter weights. Other-author negatives remain distinct from the positive reference bank. Model eligibility and grouped validation are defined in the [specification](specification.md); [negative collection](negative-corpus.md) preserves public source licensing and provenance.

More pooled examples do not establish improved accuracy. Topic, length, formatting, and genre differences can explain discrimination. Scores remain style compatibility rather than authorship probability. Private inputs and generated artifacts must stay ignored. Never publish private prose, filenames, document IDs, raw snapshots, or retrieval excerpts. Use invented fixtures and generic source labels in maintained docs; generated local reports compute counts and source metrics automatically.

## Domain-matched negatives and invalidation

Downloaded historical email and AI/ML article bodies live in the ignored `negative_posts/local/` subtree, with raw snapshots and provenance under ignored acquisition artifacts. Public blog attribution belongs in the maintained source inventory; detailed email selectors remain local. Keep private other-author email inputs in the ignored `negative_posts/email/` subtree, or an independently ignored directory. Public blog samples retain their source licenses and attribution. Human other-author negatives remain limited to email bodies and technical AI/ML blog prose with similar audience and genre; explicitly reviewed `ai_synthetic` prose is also eligible. Formal specifications, PEPs, RFCs and documentation are excluded. Email cleanup removes quotations, headers, signatures and boilerplate so only newly authored prose contributes. Stable author identity keeps all one person’s messages/posts in one validation group; `source_type` identifies `email`, `technical_blog` or `ai_synthetic` for diagnostics, never prediction.

Replacing negative sources requires fresh evaluation and production artifacts, including views, reference banks, vocabulary, verifier, calibration and thresholds. Unchanged-text embeddings with valid keys may be retained. Historical performance from an easier former population does not measure the same task. Consult [negative collection and licensing](negative-corpus.md) for manually curated eligible sources and retained historical attribution.

## Synthetic storage and ancestry

Approved synthetic negatives belong under `negative_posts/ai/tracked/` only when their complete ancestry is affirmatively Git-tracked. The ignored `negative_posts/ai/untracked/` directory holds descendants of private, ignored or otherwise untracked roots. An ignored ancestor permanently taints every descendant, including generations from copied synthetic parents: provenance is transitive and irreversible. The helper computes placement; no override exists. Rejected attempts and local provenance/review records stay in ignored `artifacts/ai_negative_generation/`.

Each synthetic file records `source_type: ai_synthetic`, `human_authored: false`, parent ID/hash, generator/attempt and visibility. Its `author_id` and `synthetic_lineage_id` identify the original positive source lineage, so every related root stays together in evaluation. Generators do not receive repository criteria; use isolated contexts and neutral source prompts. For private sources, choose an explicitly permitted environment before sharing anything. Initial generation here can use public tracked positives exclusively. See [blind curation](negative-corpus.md#blind-synthetic-curation) for deterministic tooling and manual review.
