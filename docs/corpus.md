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
