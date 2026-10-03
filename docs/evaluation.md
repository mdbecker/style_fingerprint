# Grouped development evaluation and frozen production configuration

Evaluation selects model behavior from development data. Production refitting applies those frozen choices to approved writing. The already inspected holdout remains historical evidence and must never guide feature, threshold, weighting, segmentation or hyperparameter changes.

## Split policy and isolation

The seeded historical split targets at least half the blog inventory, rounded up, and at least three blogs where available; other positive sources and negatives target 20%, rounded up. Independent roots, known negative authors and connected duplicate-prose groups stay together. Seed 42 is the default. Sorted inventories and fixed seeded assignment ensure repeatability. Exact role identities and corpus hashes remain in ignored artifacts. Cross-label duplicate prose fails rather than implying clean attribution.

Every training view retains its permanent root identity. Positive roots and known negative authors define validation groups. No validation root enters fitted rows, character vocabulary, reference statistics, reference passages, normalization or calibration. Calibration receives one median out-of-fold margin per root, regardless of view count. Missing validation predictions are omitted, never replaced by in-sample predictions. Nested calibration/model-selection folds also preserve group isolation.

Generating more correlated views cannot increase independent sample counts. Known negative authors receive equal total influence, divided among their roots and views; positive roots receive equal total document influence. Supervision needs ten independent negative roots, at least three known negative authors when reliable author metadata exists, and enough independent positive groups for calibration. Otherwise the existing reference-similarity fallback remains explicit; operating thresholds and decisions cannot be calibrated without adequate negatives, so the result reports unavailable thresholds and INCONCLUSIVE_OR_MISMATCH.

## Model and threshold selection

Compare logistic regression and optional LightGBM using identical grouped development predictions. Prefer logistic regression unless LightGBM improves AUROC by at least 0.02 and does not materially worsen TPR at 5% FPR. Length metadata does not enter the classifier. Document predictions aggregate view margins by median before calibration.

Choose the match threshold to maximize genuine-writing acceptance under development false acceptance at most 5%. If the target cannot be met, choose the lowest attainable false acceptance and best positive acceptance within it, and report the limitation. Choose a lower mismatch threshold targeting false rejection at most 5% when data supports two thresholds. Use a distinct supported score cutoff; floating-point neighbors cannot create a meaningful inconclusive band. Scores between them are INCONCLUSIVE; sparse-data fallback below the match threshold is INCONCLUSIVE_OR_MISMATCH. Compatibility remains a 0–100 style scale, never authorship probability.

## Negative contrast and development ablations

Only human-authored other-author email bodies and technical AI/ML blogs are eligible negatives. Python PEPs, formal specifications, RFCs, standards, API/reference documentation and unrelated genres are excluded throughout training, calibration, evaluation, reference banks and reports. Preserve stable root/author identity and `source_type` (`email` or `technical_blog`); source labels and identities are diagnostic/grouping metadata, never predictor features. Email cleanup retains newly authored prose only. Author diversity matters more than raw document count.

Use the existing encoder and symmetric multi-vector comparison for one similarity per negative author. Add user embedding similarity, best and median negative-author similarities, and user-minus-best and user-minus-median gaps. Validation roots/authors are absent from negative banks and every fitted state. Hard roots derive only from grouped development OOF scores: union of scores at/above match threshold and highest-scoring 10% of negatives. An author is hard if any root is hard or author median reaches mismatch threshold.

Compare only four development configurations: baseline, baseline plus contrast, contrast plus hard-author weighting, and contrast without character predictors. Ordinary authors have total weight 1; the weighting candidate gives hard authors 2, preserving root/view balancing. Select weighting or character removal only when TPR at 5% FPR improves without AUROC declining more than 0.01 or recognition declining more than 0.03; weighting must also avoid calibration degradation. Logistic regression remains preferred under the existing challenger rule. Character measurements may remain explanatory diagnostics when classifier predictors are removed. Historical holdout never selects these choices.

Changing eligible negative inputs invalidates frozen selection and supervised artifacts. Rebuild views, banks, vocabulary, features, verifier, calibration, thresholds, predictions and production state; only valid embeddings for unchanged text may be reused. Results from the former PEP population remain historical and are not directly comparable with current performance.

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

The default HTML shows Summary, Historical holdout, Decision boundaries and optional Watch-outs, followed by collapsed Technical details. The four development summary values are recognition, false acceptance, inconclusive percentages and AUROC. Holdout emphasizes recognized/rejected counts. Visible thresholds are rounded; exact values remain in technical details. Training fit, nested selection, TPR at 1%, 5% and 10% FPR, average precision, Brier error, model/source tables and root/view counts are collapsed.

At most three difficult authors appear visibly. Technical tables show at most twenty authors sorted by false acceptance then median compatibility, and ten difficult development OOF roots. Complete diagnostics remain in `evaluation.json` and the one-row-per-root `evaluation_predictions.parquet`. Prediction rows identify development OOF versus historical holdout and record metadata, components, negative-author contrast, margin, compatibility, decision and hard status without prose. Source type supports separate email/technical-blog document counts, author counts, median compatibility and false acceptance; it is never a classifier feature.
Small datasets cannot support precise false-acceptance guarantees. Related correspondence, sparse source subsets, topic/genre confounding and unknown encoder pretraining membership limit generalization claims. More untouched independent writing is more valuable than more views of consumed roots. Model snapshots and retrieval excerpts remain private ignored artifacts; public documentation does not enumerate private input identities. See [specification](specification.md), [corpus handling](corpus.md) and [development verification](development.md).

The four visible summary cards use nested grouped model-selection metrics, estimating the complete selection process. Selected configuration OOF performance remains a diagnostic in collapsed Technical details. The single additional ablation compares hard-negative-weighted contrast with and without character predictors on identical development folds; historical holdout is informational only. See the [current specification](specification.md) for materiality thresholds and the frozen feature decision.
