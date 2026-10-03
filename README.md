# Personal writing style fingerprint

A local Python tool that compares new prose with historical blog posts in `blog_posts/` and optional private email examples, pooled into one positive dataset. It combines one pretrained LUAR authorship encoder, 95 interpretable stylometric measurements, and character 3–5 gram TF-IDF similarity. It explains differences and retrieves historical passages.

The **0–100 score measures compatibility with the supplied writing**, not the probability that you wrote it. It is not forensic proof, an AI detector, or a rewriting tool. Grouped development evaluation freezes model choices and operating thresholds before production refitting. The previously inspected holdout remains historical evidence. Results remain exploratory: the genres, lengths, and topics differ, and most emails are short.

## Install

Use Python 3.11 or newer; Python 3.13 was verified here and is recommended:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

To benchmark the optional supervised boosting model:

```sh
python -m pip install -e '.[supervised]'
```

LightGBM may need a native OpenMP runtime on macOS. If it is unavailable, the tool explicitly reports this and evaluates logistic regression. No additional transformer is substituted.

Run commands from this project directory. The first build downloads the pinned LUAR checkpoint (roughly 2.5 GB); inference then runs locally. The checkpoint includes custom model code loaded at its pinned revision. Its weights and generated outputs are ignored by Git.

## Evaluate, build, score, explain

```sh
python -m style_fingerprint evaluate
python -m style_fingerprint build
python -m style_fingerprint score tests/fixtures/candidate.txt
python -m style_fingerprint explain candidate.md
python -m style_fingerprint score new-email.txt --input-format email
python -m style_fingerprint evaluate
```

Useful flags:

```sh
python -m style_fingerprint build --device cpu --offline
python -m style_fingerprint build --corpus blog_posts --artifacts artifacts
python -m style_fingerprint evaluate --seed 42 --holdout-fraction .2
python -m style_fingerprint score --text "I think this is an interesting experiment."
python -m style_fingerprint explain candidate.md --json
python -m style_fingerprint evaluate --json
```

`--offline` requires an already downloaded checkpoint. CPU works; automatic device selection prefers CUDA, then MPS, then CPU. On macOS, CPU inference uses one worker thread to avoid native OpenMP crashes when the encoder and optional challenger share a process. `score` prints a compact result; `explain` includes full diagnostics. JSON scoring includes explanations. Errors are actionable and return a nonzero exit status.

## Local writing self-editor

With an existing production fingerprint and the pinned encoder already cached, run:

```sh
python -m style_fingerprint serve
```

Open `http://127.0.0.1:8000`. Paste plain prose, choose **Analyze style**, select an underlined sentence to see measured differences, and edit in the draft box. Choose **Analyze again** (or Ctrl/Cmd + Enter) to compare the new score with the previous result. Highlights show at most ten relative anomalies; the sidebar shows up to three differences and three familiar style patterns. Low/medium/high highlights use both color and underline styles. No text is rewritten for you.

Compatibility is similarity to your historical fingerprint, not authorship probability. Decisions use existing calibrated thresholds, not an arbitrary midpoint. Passage compatibility supplies context for highlighted sentences; deletion deltas measure sensitivity, not causation. Short drafts may have no sentence-deletion evidence, and no highlight does not establish a perfect match. Fewer than three words fails clearly; evidence is LOW below 150 words, MEDIUM from 150–499, and HIGH from 500, with component disagreement able to downgrade it. Topic, genre and segmentation can affect results.

The server binds to `127.0.0.1` by default and serves the self-contained page and API together. It loads the fingerprint and cached encoder once, serializes inference, and never retrains. Submitted prose is not logged, saved, sent externally, or included in artifacts; derived candidate cache entries are released after each request. Browser results and previous scores stay in page memory only; refreshing clears them. There are no external page assets or frontend build dependencies. The limit is 50,000 Unicode characters. Loading failures, invalid prose and request failures are shown without Python tracebacks. `GET /api/health` reports readiness.

Use `--port 8080` to change the port, or `--artifacts PATH` to use another existing fingerprint. The HTML source is [the packaged single page](style_fingerprint/web/index.html). This personal tool has no authentication; keep its binding local. A first encoder download must happen through the existing build workflow, before starting the self-editor.

## Python API

```python
from style_fingerprint import StyleFingerprint

fp = StyleFingerprint.build("blog_posts", build_mode="production")  # Evaluates once if absent
fp = StyleFingerprint.load("artifacts")
result = fp.score("Your candidate prose, usually several paragraphs or more...")

print(result.score, result.decision, result.evidence_strength)
print(result.match_threshold, result.mismatch_threshold)
print(result.component_scores)
print(result.strongest_matches)
print(result.largest_mismatches)
print(result.anomalous_passages)
print(result.anomalous_sentences)
print(result.nearest_reference_passages)
report = result.to_dict()
```

The Python build API retains `build_mode='evaluation'` by default for development callers; use `build_mode='production'` for frozen refitting.

`fp.score(email_text, input_format='email')` uses the same plain-text email cleaning as training, including for explanation subscores. The default remains Markdown.

`fp.score(text, explain=False)` omits passage/deletion analysis while retaining historical retrieval and measured feature deviations. `evaluate` runs grouped development evaluation, derives calibration and operating thresholds, and writes a frozen configuration plus `artifacts/report.html`. `build` consumes those choices and refits the production fingerprint on approved writing without repeating model selection. If evaluation has never run, build explicitly announces one initial evaluation.

A production fingerprint may use approved documents previously reserved for the historical holdout after configuration is frozen. A genuinely new holdout requires untouched writing designated before model inspection; a permanently excluded manifest keeps sealed roots out of all training and selection. See [evaluation details](docs/evaluation.md).

## Corpus and rebuilds

Add independent historical posts under `blog_posts/` and individually authored plain-text email examples to the configured private input directories, then evaluate and rebuild. Email discovery accepts `.txt` recursively and preserves originals. Emails are positive examples, separate from other-author negatives. See [positive corpus handling](docs/corpus.md) for cleaning, provenance, and limits. Markdown discovery accepts `.md`, `.markdown`, and `.mdown` case-insensitively. Source roots are inventories; the seeded splitter assigns development and holdout roles before fitting.

Evaluation reserves at least 50% of blogs and target 20% of each email source and negatives. Seeded source-stratified assignment keeps negative-author and copied-prose groups together. The manifest records the exact split and inventory fingerprint; loading preserves roles, while reevaluation recalculates them. Use `--seed` and `--holdout-fraction` to configure this policy. A development-only diagnostic requires `--no-holdout` (`holdout_fraction=0` in Python). See [holdout and report details](docs/evaluation.md). All historical data appeared in earlier project experiments; evaluation fitting excludes the historical holdout, but prior exposure cannot be undone. Approved historical roots may later enter the production refit.

Front matter, code, HTML markup, images, URLs, and recognized navigation/TOC content are removed. Paragraphs, headings, list prose, emphasis text, and punctuation remain. Author attribution of quoted prose cannot be inferred reliably; review quotations in your input.

Training uses deterministic paragraph-aligned views to extract more learning signal from long documents. Up to 600 words produces one full-document view; 601–1,000 produces two contiguous views plus the full document; longer roots produce up to five contiguous views plus the full document. Contiguous windows prefer 350–600 words, target at least 300 and cap at 700 without splitting sentences. Short valid documents remain one view. No root creates more than six views. Window counts are upper bounds when paragraph or sentence boundaries cannot provide enough valid distinct windows; the full document is retained exactly once.

Views retain permanent root identities and never count as independent documents. Positive roots contribute equal total weight divided across their views; known negative authors share equal total influence across their documents and views. Validation keeps every root and known negative author together. Candidate document compatibility uses the median view margin; calibration has one out-of-fold observation per root. Word count, passage count and view count do not enter style prediction.

Embeddings are cached by cleaned passage text, model identifier/revision and preprocessing/encoding versions. Unchanged rebuilds reuse embeddings. Loading uses persisted snapshots without inference; new candidate inference loads the encoder lazily.

Configured private email inputs and their nested contents must remain ignored by Git. Publishable documentation does not list their individual filenames or document IDs; exact private split metadata stays in ignored artifacts. Artifacts and explanation output may contain raw emails or excerpts; keep them private. Generated artifacts live under `artifacts/`; downloaded weights live under `.cache/`. `prototype/` is ignored and never imported. Load only artifact directories you trust: the vectorizer and verifier use Python/joblib serialization.

## Optional negative corpus

The negative corpus combines attributed public technical AI/ML blog excerpts with downloaded historical AI/ML articles and public scientific-Python engineering emails. Downloaded bodies live under the ignored `negative_posts/local/blogs/` and `negative_posts/local/email/` trees; raw snapshots and selection/provenance inventories stay under ignored artifacts. Copyrighted local training inputs are kept out of Git, and public availability is not recorded as a redistribution license. Supported negatives are other authors’ natural email bodies and technical AI/ML blogs; Python PEPs, specifications, RFCs, documentation and other unrelated genres are intentionally excluded. Easy genre-separated negatives can produce misleadingly optimistic discrimination. Negative authors should resemble plausible alternative writers. See [sources, licenses, collection steps, and limitations](docs/negative-corpus.md). Add other authors' **real** comparable Markdown posts with `author:` and a stable `author_id:` in YAML front matter; keep article URL and license attribution alongside them. The sibling directory is discovered automatically, or use `build --negative-corpus PATH`.

Supervision requires at least 10 independent negative documents and at least three distinct negative authors when reliable author metadata exists. Fewer known authors disables supervision rather than silently downgrading to document-only validation. Six independent development positives are needed for grouped calibration; otherwise the tool remains in reference-similarity mode. Duplicate prose does not add independent evidence.

Grouped development predictions compare logistic regression with optional LightGBM over derived style features. LightGBM is selected only for AUROC improvement of at least 0.02 without materially worsening TPR at 5% FPR. Calibration uses root-level held-out margins. Historical public SciPy-Dev messages are selected by sender and exact message identity, retaining whole newly authored bodies after cleaning rather than concatenating threads. Collection is explicit and curated; runtime builds never scrape or download negatives. The report shows per-negative-author performance and difficult development negatives ranked by OOF compatibility, with metrics and identifiers rather than prose. Grouped development OOF diagnostics identify hard roots at the match threshold or in the highest-scoring 10% of negatives, whichever gives the larger set. A development ablation compares ordinary author balancing with 2× total weight for hard authors; weighting changes only when the measured selection criteria are met.

Author diversity matters more than raw document count: aim for 15–30 relevant authors and several documents per author where practical, without treating this as a runtime requirement. Multiple messages/posts from one person remain one validation author group. Set stable `author_id` and `source_type: email` or `source_type: technical_blog` metadata; email negatives use the email cleaner to remove headers, quotations, signatures and boilerplate. Source type exists for grouped diagnostics, never as a classifier feature.

Negative-reference banks compare the candidate with known negative authors using the same frozen encoder. The verifier receives user similarity, best and median negative-author similarity and the two user-minus-negative gaps. Validation authors never enter their own fold’s bank. Five development comparisons cover the current baseline, contrast, contrast plus hard-author weighting, contrast without character predictors, and contrast plus hard-author weighting without character predictors. Character similarity can remain diagnostic after its classifier features are removed. Principal selection metric is TPR at 5% FPR; AUROC, recognition and calibration guard against regressions.

The final weighted character ablation retains character predictors only for a TPR at 5% FPR gain of at least 0.02, an AUROC gain greater than 0.01, or a positive acceptance gain greater than 0.03. Otherwise the selected weighted verifier excludes character predictors. Persist `character_features_enabled` with the frozen schema; production consumes that decision without repeating selection. Only grouped development metrics determine this choice. MVP v1 is frozen; further model changes require newly discovered authentic positive writing or genuinely new unseen negative authors.

Changing the negative corpus invalidates frozen evaluation and supervised production artifacts; reevaluate and rebuild views, banks, vocabulary, features, verifier, calibration, thresholds and reports. Only valid unchanged-text embedding caches may be reused. Old PEP-population results are historical and cannot be compared as the same evaluation task.

## Understanding results

Nested evaluation selects operating thresholds inside each outer training fold and applies them only to that fold’s validation roots. Visible decision metrics estimate the complete model and threshold-selection process; AUROC uses combined outer scores. Production thresholds are selected afterward from all development grouped OOF predictions. Historical holdout remains excluded from selection. MVP v1 is frozen; future improvements require genuinely new positive writing or unseen negative authors, without further tuning on the existing development or historical-holdout datasets.

Without sufficient negatives, each component is normalized against leave-one-document-out historical similarities. The fixed ensemble weights are embedding **0.60**, stylometry **0.25**, and character **0.15**. A historical median maps to 50 for that component; this is a normalized reference scale, not an authorship probability or an empirically calibrated percentile.

The match threshold is learned from grouped development OOF root predictions to maximize positive acceptance while targeting false acceptance at most 5%. A lower mismatch threshold targets false rejection at most 5% where data supports it. Results expose MATCH, INCONCLUSIVE or MISMATCH and both thresholds. INCONCLUSIVE means compatibility falls between the operating thresholds. Sparse-data fallback returns INCONCLUSIVE_OR_MISMATCH below the match threshold. The score 50 is not an inherently meaningful decision boundary; reports disclose unattainable targets and limited evidence.

Evidence strength is LOW below 150 usable words, MEDIUM from 150–499, and HIGH at 500 or more. A component spread of at least 0.65 downgrades it one level. HIGH describes text length and signal agreement, not certainty about identity. Fewer than three usable words cannot be scored.

Explanations report five closest measurements and five largest relative deviations, signed component/verifier contributions, the three lowest-scoring passages, and the top three unique historical analogues **overall**. Sentence deletion is limited to twenty sentences inside at most three suspicious passages. Positive deletion deltas describe score sensitivity, not a causal judgment about individual sentences.

More independent historical documents improve reliability more than making more chunks from the same post. Match the reference genre to the intended use. Character vocabulary and authorship embeddings can encode topic; same-topic and different-topic negatives are valuable. No semantic control encoder or transformer fine-tuning is included.

## Development and documentation

```sh
python -m pytest
python -m pytest -m integration tests/test_integration.py
```

The default suite replaces only the pretrained encoder boundary; it needs no model downloads. The opt-in integration test requires the cached real checkpoint and runs on CPU. Development follows tests-first red → green stages. Generated transcripts and metrics belong in ignored `artifacts/`; maintained docs contain one concise verification note. Run `python scripts/check_docs.py` to validate documentation inventory and links.

Open `artifacts/report.html` for a compact Summary, Historical holdout, Decision boundaries and optional Watch-outs. Native collapsed Technical details retain evaluation tables, at most twenty authors and ten difficult roots. The visible summary names at most three difficult authors. `evaluation.json` stores complete evaluation metadata; `evaluation_predictions.parquet` stores one prose-free row per root, explicitly marked `development_oof` or `historical_holdout`. Independent-root and generated-view counts are computed separately from current inputs.

Visible report metrics estimate the complete model and threshold-selection process using grouped cross-validation. Selected-configuration OOF metrics are diagnostic and remain under Technical details. Character features enter the final weighted supervised verifier only when the final development ablation demonstrates the value defined above.

See [the documentation index](docs/README.md) for the current specification, architecture, score math, privacy rules, and concise verification note.

### Apple Silicon and fast editing

Use native arm64 Python and native arm64 PyTorch on Apple Silicon. Check the
installation with:

```python
import platform
import torch
print(platform.machine())
print(torch.backends.mps.is_built())
print(torch.backends.mps.is_available())
```

The target environment reports `arm64`, `True`, `True`. Run `python -m
style_fingerprint serve --device auto`; `build` and `evaluate` accept the same
option. Auto prefers CUDA, then MPS, then CPU. Explicit `--device mps` fails
when unavailable. Do not enable `PYTORCH_ENABLE_MPS_FALLBACK`: unsupported GPU
operations should surface clearly. If health reports CPU, check native Python,
MPS availability and the device option; use a compatible native PyTorch install.

The editor shows the actual device in its small readiness indicator. GPU startup
warms the encoder before readiness, reducing the first-request delay. GPU
acceleration affects transformer embeddings; logistic regression and stylometry
remain on CPU. GPU batches default to 16, CPU batches to 4; one GPU OOM retry
reduces 16 to 8. Embedding output preserves input order.

Analyze style defaults to FAST: document scoring, passage evidence, deviations
and reference comparisons, with no sentence deletion. Select **Deep analysis
(slower)** for bounded counterfactual rescoring (three passages, twenty sentences).
The result displays request duration. `/api/analyze` accepts `mode: "fast"` or
`"deep"` and returns `analysis_mode` and `timing_ms`; `/api/health` reports actual
`device`, `dtype` and `embedding_batch_size`.

Existing fingerprints retain FP32. Internal `Config(encoder_dtype='float16')`
supports an explicit precision experiment/rebuild; changing precision requires
reevaluation and rebuilt reference embeddings. Dtype participates in cache keys;
device does not. Moving an unchanged FP32 fingerprint from CPU to MPS requires
no rebuild. FP16 is not the default without measured acceptance: complete decision
agreement, mean/max score drift at most 0.5/1.5 points, AUROC decline and Brier
degradation at most 0.005, and at least 20% warm latency improvement.

Run `.venv/bin/python scripts/benchmark_style.py --precision-experiment` on the
target machine. It measures repeated warm median encoder and FAST/DEEP times for
300, 1,000 and 2,000 words, excluding load/download/warm-up. It compares CPU FP32,
MPS FP32 and MPS FP16 where available, and measures preflight tokenization.
Precision validation refreshes reference vectors and scores frozen examples with
the same fitted verifier; it performs no selection or training. Results remain
in ignored `artifacts/performance/benchmark.json`. The benchmark does not change
model defaults automatically. Target medium encoder speedup is 2×; FAST targets
are 3.5 seconds for 1,000 words and 6 seconds for 2,000. Profile tokenization before
changing its interface; remove duplicate work only if it accounts for at least
5% of FAST latency. MLX, GGUF and model replacement remain deferred.
