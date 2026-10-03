# Implemented MVP decisions

## Scope

The [current specification](specification.md), based on the original addendum and subsequent user instructions, replaces the original PRD's semantic encoder, large feature inventory, transformer ensembles, standalone SVM, default boosting, many-module architecture, vector index/database, exhaustive sentence deletion, and tests-last priority list. The three existing style signals remain available, with compact negative-author contrast derived from the existing encoder; development ablation may remove character predictors from the verifier. The subsequent self-editor requirement adds a minimal local REST interface; no Docker, LLM explanation, AI detector, neural verifier, fine-tuning, synthetic author negatives, or automatic negative acquisition was added.

Split, grouped evaluation and aggregate report helpers live in `holdout.py`, `evaluation.py` and `report.py`. The core package consists of `config.py`, `corpus.py`, `features.py`, `embeddings.py`, `model.py`, `explain.py`, `cli.py`, and minimal package/CLI entry points, plus `web.py` and one packaged `web/index.html` for the local self-editor. Plain functions and dataclasses are used; there are no registries, service abstractions, or plugin frameworks. `prototype/` is ignored, reference-only and never a runtime dependency.

## Historical data

Training Markdown files are discovered recursively. Original posts remain in the source inventory; the seeded splitter assigns development and mixed-class final holdout roles. IDs are relative source paths. Raw Markdown, cleaned text, source paths, SHA-256 file hashes, and YAML metadata (including author/date when provided) persist. Empty corpora and files without usable prose fail with the offending path.

Cleaning strips front matter, fenced and indented code, inline code, Octopress code/highlight tags, images, HTML tags/script/style/navigation/pre content, URLs, reference-link definitions, recognized navigation, and generated TOCs. It preserves link labels, headings, list-item prose, emphasis text, paragraph breaks, and punctuation. It does not pretend to infer quotation provenance. This is a conservative local regex/Markdown pipeline, not a complete CommonMark parser; unusually complex Markdown and HTML should be reviewed.

Encoder passage grouping targets 300 words without overlapping windows; these encoding passages are distinct from the supervised training views described below. Short tails under 100 words merge with the preceding group when the merged group remains at most 700 words. An entire short document stays scorable. Very large paragraphs split at sentence boundaries where possible, otherwise word boundaries. A tiny tail may remain when a merge would exceed the hard maximum. Every passage carries document ID, passage index, exact cleaned-text character offsets, and word count. Sentence spans also refer to cleaned text, with zero-based indexes. Common abbreviations and decimal numbers are handled conservatively; this is not a full linguistic parser.

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

Per-document comparisons are retained and their median is the primary embedding signal. The supervised comparison vector also includes mean, standard deviation, minimum/maximum, and 10/25/75/90th percentiles. Retrieval uses direct NumPy cosine matrices and retains the top three unique passages overall with source, passage index, excerpt, offsets, and similarity.

## Stylometry and character signal

There are 95 stable features: sentence/paragraph rhythm, word lengths/distribution, type/token measures, hapax rate, function words, pronouns, contractions, punctuation, parentheticals, question sentences, initial conjunctions, transitions, hedges, intensifiers, subordinate markers, capitalization, headings/lists/quotes, and simple lexical-density/passive proxies. No additional POS model is installed. Proxy names explicitly avoid claiming grammatical certainty or identifying rhetorical intent from punctuation alone.

Rates ending in `_rate` are generally counts per 1,000 words, except explicitly defined sentence/paragraph fractions; length features use words, word-length features use characters, and fractions/ratios use 0–1 where appropriate. `root_type_token_ratio` is vocabulary size divided by sqrt(word count). Details live in the compact `extract_features` function.

Historical feature statistics weight independent documents equally, not their chunk counts. Each deviation includes candidate value, historical mean/median/std, historical percentile, robust z, variability flag, readable label, and description. Let median be m, document SD s, and scaled MAD d:

```
scale = max(d, 0.25*s, max(0.1*abs(m), 0.01))
robust_z = (candidate-m)/scale
stylometry_similarity = exp(-mean(min(abs(z),8))/2)
```

The explicit floor prevents zero-MAD features from generating infinite deviations with sparse data. Constant features are flagged; feature explanations prioritize nontrivial measurements when available. Five matches and five largest relative deviations are reported. An apparent "largest mismatch" may still be within the usual range when all measurements agree; descriptions remain truthful.

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

## Hierarchical supervised verifier and evaluation

Training views preserve permanent root and known negative-author identities. Paragraph-aligned deterministic contiguous windows prefer 350–600 words, target at least 300, and cap at 700 without splitting sentences. Sources up to 600 words have one full view, 601–1,000 have two contiguous plus one full view, and longer sources have up to five contiguous plus one full view. Full-document views preserve original prose. At most six views belong to a root.

Positive roots share equal total weight divided among views. Known negative authors share equal total influence divided among roots and views; unknown negatives use root weights. Word count, raw characters, passage count and view count are excluded from predictor vectors. The compact feature schema retains embedding comparison summaries, stylometric deviations and character similarity.

Supervision requires ten independent negative roots, three known negative authors when reliable metadata exists, and enough positive roots for grouped calibration. `evaluation.py` owns grouped development model comparison, root-level OOF calibration, metrics and threshold selection. Every fold excludes validation roots/authors from training rows, fitted references, vocabulary, statistics, normalization and calibration. Missing OOF margins are never replaced by training predictions.

Logistic regression remains the default. Optional LightGBM must improve grouped AUROC by at least 0.02 without materially worsening TPR at 5% FPR. Median view margins form root predictions and calibration observations. Operational thresholds use development OOF roots alone: maximize positive acceptance under 5% false acceptance; derive a lower mismatch threshold under 5% false rejection where supported. Sparse samples use an explicit single-threshold fallback. Report TPR at 1%, 5% and 10% FPR, AUROC, average precision, Brier error and inconclusive rates.

Evaluation persists frozen model/schema/view/calibration/threshold choices. Production build refits approved data using those choices without model reselection; approved historical holdout material may be included, but permanently sealed holdout-manifest roots remain excluded. Saved report and evaluation prediction tables contain diagnostics and identifiers only, never source prose. See [evaluation](evaluation.md) for discipline and [specification](specification.md) for current requirements.

Logistic coefficient and native LightGBM contribution explanations describe verifier margins, rather than additive calibrated score points. Reference-mode contributions remain weighted normalized component scores. No extra explainer model is used.

## Negative contrast and development ablations

Only human-authored other-author email bodies and technical AI/ML blogs are eligible negatives. Python PEPs, formal specifications, RFCs, standards, API/reference documentation and unrelated genres are excluded throughout training, calibration, evaluation, reference banks and reports. Preserve stable root/author identity and `source_type` (`email` or `technical_blog`); source labels and identities are diagnostic/grouping metadata, never predictor features. Email cleanup retains newly authored prose only. Author diversity matters more than raw document count.

Use the existing encoder and symmetric multi-vector comparison for one similarity per negative author. Add user embedding similarity, best and median negative-author similarities, and user-minus-best and user-minus-median gaps. Validation roots/authors are absent from negative banks and every fitted state. Hard roots derive only from grouped development OOF scores: union of scores at/above match threshold and highest-scoring 10% of negatives. An author is hard if any root is hard or author median reaches mismatch threshold.

Compare only five development configurations: baseline, baseline plus contrast, contrast plus hard-author weighting, contrast without character predictors, and contrast plus hard-author weighting without character predictors. Ordinary authors have total weight 1; the weighting candidate gives hard authors 2, preserving root/view balancing. The existing four-way selection remains unchanged. Select weighting or unweighted character removal only when TPR at 5% FPR improves without AUROC declining more than 0.01 or recognition declining more than 0.03; weighting must also avoid calibration degradation. Logistic regression remains preferred under the existing challenger rule. Character measurements may remain explanatory diagnostics when classifier predictors are removed. Historical holdout never selects these choices.

The final weighted character ablation retains character predictors only for a TPR at 5% FPR gain of at least 0.02, an AUROC gain greater than 0.01, or a positive acceptance gain greater than 0.03. Otherwise the selected weighted verifier excludes character predictors. Persist `character_features_enabled` with the frozen schema; production consumes that decision without repeating selection. Only grouped development metrics determine this choice. MVP v1 is frozen; further model changes require newly discovered authentic positive writing or genuinely new unseen negative authors.

Changing eligible negative inputs invalidates frozen selection and supervised artifacts. Rebuild views, banks, vocabulary, features, verifier, calibration, thresholds, predictions and production state; only valid embeddings for unchanged text may be reused. Results from the former PEP population remain historical and are not directly comparable with current performance.

## Anomalies and public results

`StyleFingerprint.build(...)`, `.load(...)`, `.score(text)`, and `.evaluate()` form the public workflow. `StyleScore` includes score, decision, match/mismatch thresholds, raw score, evidence, word count, components, deviations, strongest matches/mismatches, anomalous passages/sentences, analogues, best documents, and diagnostics. `to_dict()` is JSON-compatible. Supervised raw score is the model margin; reference-mode raw score is the weighted normalized similarity.

Full scoring evaluates passages individually and surfaces up to three lowest-scoring passages. "No close analogue" means nearest embedding similarity normalizes below 0.1 on the historical embedding distribution. Lowest-scoring passages are relative anomalies even when the whole document matches well. Tails with fewer than three words that cannot merge at the maximum boundary are flagged as individually unscorable (`score: null`) rather than breaking a valid whole-document result. Only the selected suspicious passages receive sentence-deletion checks, at most twenty total. Each deletion rescoring compares the whole candidate without that sentence, retains its structural heading/list source, and records `score_without - original_score` on the 0–100 scale. Only positive deltas are returned. These are sensitivity measurements and paragraph/segmentation effects can contribute.

Compact scoring omits anomaly/deletion work but still returns analogues and measured deviations. The default API includes full explanations. Explanations require no LLM and use no semantic embeddings.

## Persistence, caches, errors, and hygiene

Artifacts are `manifest.json`, `passages.parquet`, `embeddings.npy`, `vectorizer.joblib`, `evaluation.json`, `evaluation_config.json`, `evaluation_predictions.parquet`, `report.html`, and `verifier.joblib` only when trained. The manifest includes package and feature/preprocessing/encoding schema versions, source file hashes, model ID/revision, seed, config, timestamp, mode/warnings, raw/cleaned documents/metadata, document features, cache statistics, and artifact hashes. Parquet contains passage offsets/text/source, feature vectors, sentence spans, and embedding cache keys. NumPy embedding rows align exactly with passage rows. Vectorizer/verifier use trusted local joblib serialization.

Embedding keys hash cleaned passage text + model ID + pinned revision + preprocessing/encoding versions. Rebuilds read the preceding artifact bank, retain valid unchanged vectors, and compute only missing unique passages. A different model/revision or preprocessing/encoding version invalidates those vectors. Config changes that do not affect frozen embedding values (e.g. random seed) do not discard otherwise identical cached vectors. Cheap document features are refreshed on build and persisted for reuse on load. Rebuilding is explicit; `load` evaluates the saved corpus even if source files later change.

Artifact SHA-256 checks and schema/model checks reject corrupt or mixed saved files. A failed/incompatible prior build is rebuilt instead of reused. The manifest is written last, so partial saves are detectable; saving is not a transactional database or a concurrent-build service. A stale verifier is removed when rebuilding in similarity mode.

Warnings cover a small corpus, absent/inadequate negatives, short candidates, component disagreement, and unavailable optional LightGBM. Errors cover no posts, prose-free documents, unusable candidates, failed pretrained inference, oversized model-token passages, and incompatible/corrupt/missing artifacts.

Private sources, caches, prototype material, generated models, reports, and verification logs are ignored. Public fixtures are invented. Do not initialize a repository or publish private artifacts implicitly.

## Self-editor interface

The same scoring path accepts `input_format='plain'`, retaining exact source offsets. Paragraph grouping handles trailing whitespace and CRLF without cleaning away original characters. `web.py` adapts existing passage and sentence-deletion explanations into at most ten nonoverlapping sentence ranges and omits historical retrieval excerpts/identifiers. Compatibility shown for a sentence is labelled passage context. Severity uses existing positive sensitivity/gaps (low below 2 points, medium 2–under 5, high at least 5). No second classifier, explanation algorithm or encoder is used.

The FastAPI lifespan loads a production fingerprint and cached encoder once; missing/incompatible state produces a safe unavailable health/result response. A process-local lock serializes scoring. Original embedding cache state is restored even after failure, avoiding retained candidate vectors. Analysis does not save, train or mutate artifacts or thresholds. Bounded request parsing, safe errors, disabled access logs, same-origin fetches, no-store responses and an inline-assets content policy support local privacy. The single page uses an ordinary textarea plus an escaped highlighted snapshot, code-point offsets, keyboard-accessible highlights, explicit stale/loading states and in-memory comparison. The page is packaged with Python so installed `serve` retains access to it.

Runtime device resolution is independent of stored build configuration. The
encoder persists precision, uses inference mode, length-orders batches and
restores caller order, with one 16-to-8 GPU OOM retry. Server preparation warms
GPU kernels before exposing readiness. FAST explanations omit bounded sentence
deletion; DEEP retains it. The API reports runtime state and request duration.
The warm developer benchmark is `scripts/benchmark_style.py`; its local output
and precision-gate metrics belong in ignored artifacts. No precision promotion
is justified until the gate has measured evidence.
