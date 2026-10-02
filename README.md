# Personal writing style fingerprint

A local Python tool that compares new prose with historical blog posts in `blog_posts/` and positive documents in `work_corpus/` and `gmail_corpus/`, pooled into one dataset. It combines one pretrained LUAR authorship encoder, 95 interpretable stylometric measurements, and character 3–5 gram TF-IDF similarity. It explains differences and retrieves historical passages.

The **0–100 score measures compatibility with the supplied writing**, not the probability that you wrote it. It is not forensic proof, an AI detector, or a rewriting tool. The available corpus contains six blogs, 45 work emails, 18 Gmail documents, and 100 negatives. Seed 42 reserves a mixed holdout of 3 blogs, 9 work emails, 4 Gmail documents, and 20 negatives. The remaining 53 positives and 80 negatives form the development pool. Results remain exploratory: the genres, lengths, and topics differ, and most emails are short.

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

## Build, score, explain, evaluate

```sh
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
python -m style_fingerprint build --seed 42 --holdout-fraction .2
python -m style_fingerprint score --text "I think this is an interesting experiment."
python -m style_fingerprint explain candidate.md --json
python -m style_fingerprint evaluate --json
```

`--offline` requires an already downloaded checkpoint. CPU works; automatic device selection prefers CUDA, then MPS, then CPU. `score` prints a compact result; `explain` includes full diagnostics. JSON scoring includes explanations. Errors are actionable and return a nonzero exit status.

## Python API

```python
from style_fingerprint import StyleFingerprint

fp = StyleFingerprint.build("blog_posts")  # Includes sibling emails/negatives and reserves a seeded mixed holdout
fp = StyleFingerprint.load("artifacts")
result = fp.score("Your candidate prose, usually several paragraphs or more...")

print(result.score, result.evidence_strength)
print(result.component_scores)
print(result.strongest_matches)
print(result.largest_mismatches)
print(result.anomalous_passages)
print(result.anomalous_sentences)
print(result.nearest_reference_passages)
report = result.to_dict()
```

`fp.score(email_text, input_format='email')` uses the same plain-text email cleaning as training, including for explanation subscores. The default remains Markdown.

`fp.score(text, explain=False)` omits passage/deletion analysis while retaining historical retrieval and measured feature deviations. `fp.evaluate()` reruns development cross-validation using persisted role assignments and reports the mixed-class holdout separately. Build and CLI evaluation automatically write `artifacts/report.html`, with training fit, development cross-validation, holdout metrics, and holdout breakdown by source. Holdout examples never determine fitting, model selection, or calibration.

## Corpus and rebuilds

Add independent historical posts under `blog_posts/` or your individually authored plain-text emails under `work_corpus/` or `gmail_corpus/`, then rebuild. Both email directories accept `.txt` recursively and preserve the raw originals. Emails are positive examples, separate from negative-author samples. See [combined positive data](docs/corpus.md) for cleaning, provenance, per-genre evaluation, and limits. Use `--work-corpus PATH` and `--gmail-corpus PATH` to override roots. Disable both with `--no-work-corpus --no-gmail-corpus` for a blog-only build (`work_dir=False, gmail_dir=False` in the API). Discovery is recursive and accepts `.md`, `.markdown`, and `.mdown` case-insensitively. Each file retains its identity and metadata. All six original `.markdown` files are unchanged under `blog_posts/`. Source roots are complete inventories; the seeded splitter assigns roles before fitting.

Builds reserve at least 50% of blogs and target 20% of each email source and negatives. Seeded source-stratified assignment keeps negative-author and copied-prose groups together. The manifest records the exact split and inventory fingerprint; loading preserves roles, while rebuilding recalculates them. Use `--seed` and `--holdout-fraction` to configure this policy. A development-only diagnostic requires `--no-holdout` (`holdout_fraction=0` in Python). See [holdout and report details](docs/evaluation.md). All data appeared in earlier project experiments; current fitting excludes the holdout, but historical exposure cannot be undone.

Front matter, code, HTML markup, images, URLs, and recognized navigation/TOC content are removed. Paragraphs, headings, list prose, emphasis text, and punctuation remain. Author attribution of quoted prose cannot be inferred reliably; review quotations in your input.

Passages group adjacent paragraphs without overlapping windows, aiming for 300 words. Short tails merge when possible and oversized paragraphs split at sentence/word boundaries at 700 words. Embeddings are cached by cleaned passage text, model identifier/revision, and preprocessing/encoding versions. Rebuilding an unchanged corpus reuses embeddings; changing one passage recomputes only affected unique passages. Loading uses persisted text/features/vocabulary without model inference; the model loads lazily for new candidate text.

Private inputs in `/work_corpus/` and `/gmail_corpus/`, including every nested file, are ignored by Git. Publishable documentation does not list their individual filenames or document IDs; exact private split metadata stays in ignored artifacts. Artifacts and explanation output may contain raw emails or excerpts; keep them private. Generated artifacts live under `artifacts/`; downloaded weights live under `.cache/`. `prototype/` is ignored and never imported. Load only artifact directories you trust: the vectorizer and verifier use Python/joblib serialization.

## Optional negative corpus

The supplied `negative_posts/` contains 100 attributed excerpts: the original 12 blog articles plus 88 independently authored, explicitly public-domain Python proposals. See [sources, licenses, collection steps, and limitations](docs/negative-corpus.md). Add other authors' **real** comparable Markdown posts with `author:` and a stable `author_id:` in YAML front matter; keep article URL and license attribution alongside them. The sibling directory is discovered automatically, or use `build --negative-corpus PATH`.

Supervision requires at least 10 distinct negative documents; author count is not an eligibility restriction. Known author groups are used for evaluation when at least three are available, otherwise documented whole-document holdouts are used. Duplicate prose does not count as extra independent documents. At least six independent positive documents are required for the nested calibration procedure. Otherwise the tool stays in reference-similarity mode.

The supervised path uses nested stratified group cross-validation with inner model choice and calibration, and compares logistic regression with LightGBM over derived comparison features. All positive sources share one class with equal document weight in training and calibration; no source gets extra weight. Historical reference statistics continue to weight documents equally. LightGBM is selected only when its grouped validation AUROC improves by at least 0.02. Calibration uses held-out margins with equal total mass per class, independent of fold sample counts; the result remains style compatibility. Evaluation exports author holdouts and per-author results, and warns when one author dominates. Collection is an explicit curated operation; builds never fetch negative writing. Rebuild existing artifacts to adopt the new corpus and calibration behavior.

## Understanding results

Without sufficient negatives, each component is normalized against leave-one-document-out historical similarities. The fixed ensemble weights are embedding **0.60**, stylometry **0.25**, and character **0.15**. A historical median maps to 50 for that component; this is a normalized reference scale, not an authorship probability or an empirically calibrated percentile.

Evidence strength is LOW below 150 usable words, MEDIUM from 150–499, and HIGH at 500 or more. A component spread of at least 0.65 downgrades it one level. HIGH describes text length and signal agreement, not certainty about identity. Fewer than three usable words cannot be scored.

Explanations report five closest measurements and five largest relative deviations, signed component/verifier contributions, the three lowest-scoring passages, and the top three historical analogues **per candidate passage**. Sentence deletion is limited to twenty sentences inside at most three suspicious passages. Positive deletion deltas describe score sensitivity, not a causal judgment about individual sentences.

More independent historical documents improve reliability more than making more chunks from the same post. Match the reference genre to the intended use. Character vocabulary and authorship embeddings can encode topic; same-topic and different-topic negatives are valuable. No semantic control encoder or transformer fine-tuning is included.

## Development and documentation

```sh
python -m pytest
python -m pytest -m integration tests/test_integration.py
```

The default suite replaces only the pretrained encoder boundary; it needs no model downloads. The opt-in integration test requires the cached real checkpoint and runs on CPU. Development follows tests-first red → green stages. Generated transcripts and metrics belong in ignored `artifacts/`; maintained docs contain one concise verification note. Run `python scripts/check_docs.py` to validate documentation inventory and links.

The verified current holdout has AUROC 0.900. At cutoff 50 it accepts 15/16 positives and 8/20 negatives (40% false acceptance); no settings were tuned to these results. Open the automatically generated local `artifacts/report.html` for training, development, and source-level holdout results.

See [the documentation index](docs/README.md) for the current specification, architecture, score math, privacy rules, and concise verification note.
