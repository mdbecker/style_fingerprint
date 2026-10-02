# Grouped development evaluation and frozen production configuration

Evaluation selects model behavior from development data. Production refitting applies those frozen choices to approved writing. The already inspected holdout remains historical evidence and must never guide feature, threshold, weighting, segmentation or hyperparameter changes.

## Split policy and isolation

The seeded historical split targets at least half the blog inventory, rounded up, and at least three blogs where available; other positive sources and negatives target 20%, rounded up. Independent roots, known negative authors and connected duplicate-prose groups stay together. Seed 42 is the default. Sorted inventories and fixed seeded assignment ensure repeatability. Exact role identities and corpus hashes remain in ignored artifacts. Cross-label duplicate prose fails rather than implying clean attribution.

Every training view retains its permanent root identity. Positive roots and known negative authors define validation groups. No validation root enters fitted rows, character vocabulary, reference statistics, reference passages, normalization or calibration. Calibration receives one median out-of-fold margin per root, regardless of view count. Missing validation predictions are omitted, never replaced by in-sample predictions. Nested calibration/model-selection folds also preserve group isolation.

Generating more correlated views cannot increase independent sample counts. Known negative authors receive equal total influence, divided among their roots and views; positive roots receive equal total document influence. Supervision needs ten independent negative roots, at least three known negative authors when reliable author metadata exists, and enough independent positive groups for calibration. Otherwise the existing reference-similarity fallback remains explicit; operating thresholds and decisions cannot be calibrated without adequate negatives, so the result reports unavailable thresholds and INCONCLUSIVE_OR_MISMATCH.

## Model and threshold selection

Compare logistic regression and optional LightGBM using identical grouped development predictions. Prefer logistic regression unless LightGBM improves AUROC by at least 0.02 and does not materially worsen TPR at 5% FPR. Length metadata does not enter the classifier. Document predictions aggregate view margins by median before calibration.

Choose the match threshold to maximize genuine-writing acceptance under development false acceptance at most 5%. If the target cannot be met, choose the lowest attainable false acceptance and best positive acceptance within it, and report the limitation. Choose a lower mismatch threshold targeting false rejection at most 5% when data supports two thresholds. Use a distinct supported score cutoff; floating-point neighbors cannot create a meaningful inconclusive band. Scores between them are INCONCLUSIVE; sparse-data fallback below the match threshold is INCONCLUSIVE_OR_MISMATCH. Compatibility remains a 0–100 style scale, never authorship probability.

## Usage and artifacts

```sh
python -m style_fingerprint evaluate --json
python -m style_fingerprint build --device cpu --offline
python -m style_fingerprint score tests/fixtures/candidate.txt
python -m style_fingerprint explain tests/fixtures/candidate.txt
```

Evaluation writes frozen `evaluation_config.json`, metrics in `evaluation.json`, identifier/metric-only `evaluation_predictions.parquet`, and standalone `report.html`. Production build consumes the frozen model, schema, segmentation, calibration and threshold configuration without reselecting them. If configuration is absent, build explicitly announces automatic initial evaluation. The production fingerprint may incorporate approved historical holdout roots; doing so does not create a fresh independent benchmark.

A permanently excluded holdout manifest supports future sealed data. Designate genuinely new historical positives and negatives as `holdout_v2` before inspection. Pass `--holdout-manifest PATH` to evaluation; the JSON object uses `{"holdout_v2": ["generic-document.md", "negative/generic-author/post.md"]}` with local root IDs. The designation persists across later evaluations and builds in that artifact directory; connected duplicate and author groups are excluded too. `build --exclude-historical-holdout` keeps consumed historical test roots excluded from production as an explicit alternative.

These roots never train the verifier, reference fingerprint or calibrator, nor select model, features or thresholds. Consumed documents cannot become a genuinely new holdout by reshuffling.

## Reading the report

Reports show optimistic training fit, grouped development validation and historical holdout separately. TPR at 1%, 5% and 10% FPR are prominent alongside AUROC, average precision and Brier error. Thresholds and inconclusive rates explain operational behavior; confusion counts use the selected match threshold. Single-class source subsets have no AUROC.

Independent root counts and generated-view counts appear separately. Per-negative-author summaries show documents, mean/median/maximum compatibility and false acceptance. Difficult development negatives rank by OOF score with identifiers, word counts, margins and component scores. These are diagnostics, never automatic training-weight adjustments. No source prose appears in HTML or the evaluation prediction table.

Small datasets cannot support precise false-acceptance guarantees. Related correspondence, sparse source subsets, topic/genre confounding and unknown encoder pretraining membership limit generalization claims. More untouched independent writing is more valuable than more views of consumed roots. Model snapshots and retrieval excerpts remain private ignored artifacts; public documentation does not enumerate private input identities. See [specification](specification.md), [corpus handling](corpus.md) and [development verification](development.md).
