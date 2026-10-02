# Implemented MVP decisions

## Scope

The [current specification](specification.md), based on the original addendum and subsequent user instructions, replaces the original PRD's semantic encoder, large feature inventory, transformer ensembles, standalone SVM, default boosting, many-module architecture, vector index/database, exhaustive sentence deletion, and tests-last priority list. Exactly three style signals remain. No service, website, REST API, Docker, LLM explanation, AI detector, neural verifier, fine-tuning, synthetic author negatives, or automatic negative acquisition was added.

Split and aggregate report helpers live in `holdout.py` and `report.py`. The core package consists of `config.py`, `corpus.py`, `features.py`, `embeddings.py`, `model.py`, `explain.py`, `cli.py`, and minimal package/CLI entry points. Plain functions and dataclasses are used; there are no registries, service abstractions, or plugin frameworks. `prototype/` was absent at implementation time; it is ignored and is never a runtime dependency.

## Historical data

Training Markdown files are discovered recursively. All six original posts remain in the source inventory; the seeded splitter assigns three to development and three to the mixed-class final holdout. IDs are relative source paths. Raw Markdown, cleaned text, source paths, SHA-256 file hashes, and YAML metadata (including author/date when provided) persist. Empty corpora and files without usable prose fail with the offending path.

Cleaning strips front matter, fenced and indented code, inline code, Octopress code/highlight tags, images, HTML tags/script/style/navigation/pre content, URLs, reference-link definitions, recognized navigation, and generated TOCs. It preserves link labels, headings, list-item prose, emphasis text, paragraph breaks, and punctuation. It does not pretend to infer quotation provenance. This is a conservative local regex/Markdown pipeline, not a complete CommonMark parser; unusually complex Markdown and HTML should be reviewed.

Paragraph grouping targets 300 words and never creates overlapping windows. Short tails under 100 words merge with the preceding group when the merged group remains at most 700 words. An entire short document stays scorable. Very large paragraphs split at sentence boundaries where possible, otherwise word boundaries. A tiny tail may remain when a merge would exceed the hard maximum. Every passage carries document ID, passage index, exact cleaned-text character offsets, and word count. Sentence spans also refer to cleaned text, with zero-based indexes. Common abbreviations and decimal numbers are handled conservatively; this is not a full linguistic parser.

## Authorship encoder and comparison

The sole checkpoint is [`rrivera1849/LUAR-MUD-MV-Qwen`](https://huggingface.co/rrivera1849/LUAR-MUD-MV-Qwen), pinned to `9dea156891cbd054f8254ffea1690a9aafa0a2e2`. Its official model card and pinned implementation were inspected. It produces a 512-dimensional vector per text. Model code executes through the explicit, pinned `trust_remote_code` interface.

Each natural passage is encoded as a singleton episode with multi-vector output, then its one passage vector is retained. This keeps each cache entry independent of neighboring passages and prevents reference membership/batch context from changing embeddings. At comparison time a document is the full set of its passage vectors, never an average corpus vector. The checkpoint's episode-context attention is consequently limited to one passage at inference; that tradeoff should be evaluated on a larger independent corpus. The model was trained on short Reddit texts (32 tokens), so transferring to long technical-blog passages is an empirical limitation rather than a proven accuracy guarantee.

Passages batch four at a time. An explicit 4096-token limit rejects unusually token-heavy passages instead of silently truncating. Automatic device choice is CUDA → MPS → CPU; CPU smoke inference was verified. Missing dependencies/checkpoints, invalid vectors, or loading errors fail clearly. There is no alternative-model fallback.

The Hugging Face snapshot is resolved first and both model and tokenizer load from that local pinned path. This avoids a Transformers metadata call that violated offline loading despite `local_files_only`. The Qwen tokenizer explicitly disables an unrelated Mistral regex patch to retain its published tokenization; Transformers 4.57.6 otherwise emits a misleading warning for this locally loaded custom architecture.

For candidate passage vectors C and one reference document R:

```
symmetric_MaxSim = (mean_i max_j cosine(C_i,R_j)
                  + mean_j max_i cosine(R_j,C_i)) / 2
```

Per-document comparisons are retained and their median is the primary embedding signal. The supervised comparison vector also includes mean, standard deviation, minimum/maximum, and 10/25/75/90th percentiles. Retrieval uses direct NumPy cosine matrices and retains the top three passages per candidate passage with source, passage index, excerpt, offsets, and similarity.

## Stylometry and character signal

There are 95 stable features: sentence/paragraph rhythm, word lengths/distribution, type/token measures, hapax rate, function words, pronouns, contractions, punctuation, parentheticals, question sentences, initial conjunctions, transitions, hedges, intensifiers, subordinate markers, capitalization, headings/lists/quotes, and simple lexical-density/passive proxies. No additional POS model is installed. Proxy names explicitly avoid claiming grammatical certainty or identifying rhetorical intent from punctuation alone.

Rates ending in `_rate` are generally counts per 1,000 words, except explicitly defined sentence/paragraph fractions; length features use words, word-length features use characters, and fractions/ratios use 0–1 where appropriate. `root_type_token_ratio` is vocabulary size divided by sqrt(word count). Details live in the compact `extract_features` function.

Historical feature statistics weight independent documents equally, not their chunk counts. Each deviation includes candidate value, historical mean/median/std, historical percentile, robust z, variability flag, readable label, and description. Let median be m, document SD s, and scaled MAD d:

```
scale = max(d, 0.25*s, max(0.1*abs(m), 0.01))
robust_z = (candidate-m)/scale
stylometry_similarity = exp(-mean(min(abs(z),8))/2)
```

The explicit floor prevents zero-MAD features from generating infinite deviations with six posts. Constant features are flagged; feature explanations prioritize nontrivial measurements when available. Five matches and five largest relative deviations are reported. An apparent "largest mismatch" may still be within the usual range when all measurements agree; descriptions remain truthful.

Character 3–5 gram TF-IDF uses sublinear term frequency, a maximum vocabulary of 50,000, and passage cosine comparisons. It uses symmetric best-match aggregation per reference document, then the median across documents. Evaluation fits the vocabulary only on the reference side. No SVM is added.

## Reference-similarity scoring and evidence

The default mode needs no negatives. Leave-one-document-out raw similarities provide three historical normalization distributions. For each component x:

```
center = median(historical similarities)
scale = max(1.4826*MAD, 0.25*SD, 0.05)
normalized = sigmoid(clip((x-center)/scale, -30, 30))
score = 100 * (0.60*embedding + 0.25*stylometry + 0.15*character)
```

This is a robust normalized compatibility scale, not an exact empirical percentile and never an authorship probability. Historical medians map to 50. If no independent normalization fold is possible, raw similarity is clipped to 0–1 and the small-corpus warning remains; held-out metrics are absent rather than fabricated.

Evidence is LOW below 150 usable words, MEDIUM for 150–499, HIGH at 500+. A max-minus-min component spread at least 0.65 downgrades one level. These are deterministic evidence-length rules, not learned certainty. Candidates with fewer than three usable words fail clearly; longer short prose returns a low-evidence warning.

## Evaluation and leakage controls

Every historical document is held out as a candidate. None of its passages, feature statistics, or vocabulary enter its reference fingerprint. Normalization for the outer candidate is itself fitted with leave-one-out comparisons within the outer reference set, so the held-out document cannot leak through score calibration.

Exact duplicate passages are removed from a held-out candidate's reference. Shared paragraphs of at least twenty words also remove affected reference passages even if chunk boundaries differ. Filtering can conservatively discard surrounding prose; when all references disappear, an invalid fold is omitted. Document statistics then use retained text rather than the excluded source prose. Duplicate entire documents do not count toward supervised eligibility.

Each evaluation fold exposes candidate ID, reference IDs, statistics IDs, normalization IDs, raw components, normalized components, removed duplicate-passage count, and score. Positive-only metrics include per-document compatibility, held-out distribution, variance, minimum/mean, component disagreement, and ablations for embedding, stylometry, character, embedding+stylometry, and the three-signal ensemble. There is no semantic/full-extra-model ablation because those models are out of scope. Positive-only consistency cannot establish discrimination or optimize accuracy; the stipulated weights remain fixed.

## Optional supervised verifier

A sibling `negative_posts/` is discovered automatically; an explicit directory can also be supplied. Negatives remain separate from the positive reference bank. Supervision requires ten distinct negative prose documents. The current user policy imposes no author-count eligibility restriction; author-grouped validation is used when at least three known authors are available, otherwise document holdouts are explicitly reported. Unknown authors are grouped by document and this limitation remains explicit. The nested procedure additionally needs six independent positives; smaller samples stay in similarity mode rather than pretend that valid nested calibration is possible.

Inputs are comparison features only: the three raw signals, embedding distribution summaries, usable words/passage count, and signed robust feature deviations clipped at ±10. No raw transformer dimensions enter the classifier.

Outer stratified group folds hold out positive documents and group known negative authors together. Each training positive compares against other training positives, excluding itself; outer test positives are excluded from all training references. Inner folds within each outer training corpus produce out-of-fold margins to fit a sigmoid calibration layer. No outer test document enters this calibration. In small split configurations, deterministic two-way document/author partitions maintain independent reference documents. Fold membership is exported for audit.

Logistic regression uses standardized features, balanced class weights, C=0.1, and the configured seed. LightGBM, if installed and importable, uses a small deterministic tree model. It is selected only when grouped AUROC improves by at least 0.02. The final verifier trains on eligible development comparison rows only; its sigmoid calibrator uses outer held-out margins. Reported metrics include AUROC, average precision, approximate EER (nearest ROC crossing), TPR at 1%/5% FPR, Brier, and ten-bin expected calibration error. Candidate comparison metrics guide final model selection and are exploratory. Nested selection metrics choose each outer-fold model using inner validation only. The separately reserved mixed holdout evaluates the final model; see [evaluation](evaluation.md).

Logistic explanations are signed standardized-feature coefficients; LightGBM uses native `pred_contrib` TreeSHAP, avoiding a separate SHAP dependency. Contributions explain the uncalibrated verifier margin, not additive user-facing score points. In similarity mode weighted normalized component contributions are score points. Feature importance, both model metrics, selected model, calibration status, fold membership, and held-out scores persist.

## Anomalies and public results

`StyleFingerprint.build(...)`, `.load(...)`, `.score(text)`, and `.evaluate()` form the public workflow. `StyleScore` includes score, raw score, evidence, word count, components, deviations, strongest matches/mismatches, anomalous passages/sentences, analogues, best documents, and diagnostics. `to_dict()` is JSON-compatible. Supervised raw score is the model margin; reference-mode raw score is the weighted normalized similarity.

Full scoring evaluates passages individually and surfaces up to three lowest-scoring passages. "No close analogue" means nearest embedding similarity normalizes below 0.1 on the historical embedding distribution. Lowest-scoring passages are relative anomalies even when the whole document matches well. Tails with fewer than three words that cannot merge at the maximum boundary are flagged as individually unscorable (`score: null`) rather than breaking a valid whole-document result. Only the selected suspicious passages receive sentence-deletion checks, at most twenty total. Each deletion rescoring compares the whole candidate without that sentence, retains its structural heading/list source, and records `score_without - original_score` on the 0–100 scale. Only positive deltas are returned. These are sensitivity measurements and paragraph/segmentation effects can contribute.

Compact scoring omits anomaly/deletion work but still returns analogues and measured deviations. The default API includes full explanations. Explanations require no LLM and use no semantic embeddings.

## Persistence, caches, errors, and hygiene

Artifacts are `manifest.json`, `passages.parquet`, `embeddings.npy`, `vectorizer.joblib`, `evaluation.json`, and `verifier.joblib` only when trained. The manifest includes package and feature/preprocessing/encoding schema versions, source file hashes, model ID/revision, seed, config, timestamp, mode/warnings, raw/cleaned documents/metadata, document features, cache statistics, and artifact hashes. Parquet contains passage offsets/text/source, feature vectors, sentence spans, and embedding cache keys. NumPy embedding rows align exactly with passage rows. Vectorizer/verifier use trusted local joblib serialization.

Embedding keys hash cleaned passage text + model ID + pinned revision + preprocessing/encoding versions. Rebuilds read the preceding artifact bank, retain valid unchanged vectors, and compute only missing unique passages. A different model/revision or preprocessing/encoding version invalidates those vectors. Config changes that do not affect frozen embedding values (e.g. random seed) do not discard otherwise identical cached vectors. Cheap document features are refreshed on build and persisted for reuse on load. Rebuilding is explicit; `load` evaluates the saved corpus even if source files later change.

Artifact SHA-256 checks and schema/model checks reject corrupt or mixed saved files. A failed/incompatible prior build is rebuilt instead of reused. The manifest is written last, so partial saves are detectable; saving is not a transactional database or a concurrent-build service. A stale verifier is removed when rebuilding in similarity mode.

Warnings cover a small corpus, absent/inadequate negatives, short candidates, component disagreement, and unavailable optional LightGBM. Errors cover no posts, prose-free documents, unusable candidates, failed pretrained inference, oversized model-token passages, and incompatible/corrupt/missing artifacts.

Private sources, caches, prototype material, generated models, reports, and verification logs are ignored. Public fixtures are invented. Do not initialize a repository or publish private artifacts implicitly.