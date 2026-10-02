# Current MVP specification

This is the authoritative specification, incorporating the Generalization, Subdocument Training, Calibration, Evaluation & Maintainability Upgrade. [Repository instructions](../AGENTS.md) govern workflow. [Historical supplied specifications](historical-specifications.md) preserve earlier provenance; later explicit user instructions take precedence.

## Product and architecture

Retain the small local Python API and four commands: `evaluate`, `build`, `score FILE`, and `explain FILE`. Return 0–100 style compatibility, never authorship probability, forensic proof, or an AI-detection result. Use one frozen pinned LUAR authorship encoder, focused interpretable stylometry, and character 3–5 gram TF-IDF. Feed derived comparison features to logistic regression; never raw embedding dimensions. LightGBM is an optional challenger, selected only for grouped development AUROC improvement of at least 0.02 without materially worsening TPR at 5% FPR.

Keep plain functions and small dataclasses. Evaluation responsibilities belong in one small `evaluation.py`; no additional neural models, vector database, services, tuning framework, automatic negative acquisition, or synthetic prose. `prototype/` is reference-only and never imported by production.

## Hierarchical training and scoring

Every source has a permanent `root_document_id`; generated views, passages and rows retain it. Known negative authors retain `author_id`. Never recover these identities from generated view names. Generate deterministic paragraph-aligned contiguous views without splitting sentences: target at least 300 usable words, prefer 350–600, and cap contiguous views at 700. Valid shorter sources remain one view. Sources up to 600 words create one full view; 601–1,000 create two contiguous views plus the full document; longer sources create up to five contiguous views plus the full document. Full-document views preserve the original, even when longer than the contiguous-view limit. At most six views exist per root; overlapping windows are allowed with fixed seed. Window counts are upper bounds when no further valid paragraph or sentence windows exist, and the full document is retained exactly once.

Views add training observations, not independent documents. Each positive root contributes total weight 1, divided across its views. Known negative authors share equal influence, divided across their documents and views; unknown authors use root weighting. Independent roots remain the unit of calibration and reporting. Exclude usable word count, candidate passage count, raw character count and generated-view count from predictors. Length remains evidence metadata.

Score candidate documents using the same view generation. Compute each view's verifier margin, aggregate by median, and calibrate that root margin. Retain min, p25, median, p75, max and variance only as diagnostics. Reference-similarity fallback uses the existing three signals with weights 0.60 embedding, 0.25 stylometry and 0.15 character. Evidence is LOW below 150 words, MEDIUM from 150–499 and HIGH from 500; substantial component disagreement downgrades one level without changing compatibility. Fewer than three usable words fails clearly. Return the top three unique historical passages overall by default, using NumPy retrieval.

## Grouped evaluation and operating decisions

All validation, feature/model selection, normalization, calibration and threshold selection group positive views by root and known negative documents by author; preserve connected duplicate-prose groups. Validation roots are excluded from training rows, references, fitted statistics/vocabulary, calibration and nearest-reference candidates. Calibration uses one strictly out-of-fold median margin per root, never in-sample substitutes.

Supervision requires ten independent negative documents and six independent development positives. When reliable negative author metadata exists, require at least three distinct negative authors; otherwise remain in reference-similarity mode. Unknown authors use root groups and disclose their limitation.

Choose a match threshold from grouped development OOF root predictions to maximize positive acceptance subject to false acceptance at most 5%. If unattainable, minimize false acceptance, then maximize positive acceptance, and disclose the limitation. Derive a lower mismatch threshold targeting false rejection at most 5% where data supports it. Scores return MATCH, INCONCLUSIVE or MISMATCH; insufficient data for two distinct thresholds yields INCONCLUSIVE_OR_MISMATCH below the match threshold. The number 50 has no inherent decision meaning. Public results expose score, decision, both thresholds and evidence strength.

## Evaluation versus production

`evaluate` uses development data only to select model/schema/segmentation, calibrator and thresholds, then freezes configuration and reports. The seeded historical split reserves at least half the blogs (at least three where available), and targets 20% of other positive sources and negatives. Known authors and duplicate groups travel together. The already inspected holdout is historical evidence, never a tuning set. A future genuinely new `holdout_v2` may be designated through a permanently excluded manifest before inspection; never fabricate it from consumed data.

`build` consumes frozen choices and refits the production verifier/reference on approved material without repeating selection. Previously reserved historical material may be approved for production after evaluation choices are frozen. Permanently sealed roots remain excluded. If no frozen configuration exists, build may evaluate once, explicitly announcing this. Persist model type, feature schema, view configuration/version, calibrator, thresholds, seed, encoder/revision, hashes and evaluation/production timestamps.

## Reporting, privacy and development

Report prominently TPR at 1%, 5% and 10% FPR, AUROC, average precision, Brier error, thresholds and inconclusive rate. Show independent-root and generated-view counts separately. Record negative development/holdout identifiers, source, author, words, compatibility, margin, components and decision without prose. Include per-author count/mean/median/max/false acceptance and development OOF difficult-negative ranking; ranking never changes weights automatically.

Private source prose, filenames and IDs are never published. Local model snapshots/retrieval can contain private text; HTML and evaluation-prediction tables contain identifiers and metrics only. Keep private inputs, artifacts, caches and prototype ignored. Preserve public negative attribution, licenses and pinned provenance. Use invented fixtures. More genuinely independent writing is more valuable than additional views of existing roots.

BDD red → green → refactor is mandatory before production behavior changes. Mock only the encoder boundary in default tests; retain a marked real-model smoke test. Maintain existing docs in place, use generic private source descriptions, compute counts in ignored artifacts and keep verification in [development](development.md). Run the documentation inventory/link checker and relevant tests. See [implementation](implementation.md), [evaluation](evaluation.md), [corpus](corpus.md) and [negative licensing](negative-corpus.md).
