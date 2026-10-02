# Reproducible mixed-class holdout and evaluation report

This policy supersedes the previous manually reserved, positive-only blog test directory. All six unchanged blog originals are again under `blog_posts/`; both email directories and `negative_posts/` remain unchanged. Source directories are inventories, not role assignments. A seeded split assigns whole documents to development or final holdout before any fitted preprocessing or model training.

## Current split

| Source | Available | Development | Independent holdout |
|---|---:|---:|---:|
| blog | 6 | 3 | 3 |
| work_corpus | 45 | 36 | 9 |
| gmail_corpus | 18 | 14 | 4 |
| negative_posts | 100 | 80 | 20 |
| **Total** | **169** | **133** | **36** |

Development has 53 positives and 80 negatives; the holdout has 16 positives and 20 negatives. All positive sources still form one class with equal document weights. The holdout always targets at least half the blog inventory, rounded up, and at least three blogs when three are available (three of the current six); other sources target 20%, rounded up. Source-stratum coverage includes both email sources and negatives, so the final evaluation can report their differences.

## Determinism and group isolation

The default random seed is 42. Documents and group identities are sorted before per-source seeded shuffling (`<seed>:<source>`). Groups are selected until each source reaches its target. Connected groups join identical cleaned bodies, literal cleaned paragraphs of at least 20 words after whitespace normalization, and negative documents credited to the same normalized author identity. Entire connected groups remain on one side of the split, even across positive sources. Cross-label duplicate prose fails with an attribution error. Group constraints can overshoot a percentage target. If a valid group-disjoint mixed-class development and holdout cannot be formed, the build fails instead of silently producing misleading evaluation.

The split stores seed, fraction, algorithm version, source/content/attribution inventory fingerprint, document-to-group map, and exact role identities in the ignored artifact manifest. The aggregate documentation retains only policy, aggregate counts, and public blog roles. Identical inventory, seed, and split implementation produce the same membership regardless of filesystem iteration order. Added/removed IDs or changed grouping can alter membership. A content or metadata change updates the inventory fingerprint even when membership happens to remain the same. A split is regenerated on rebuild; loading and evaluation use the persisted snapshot.

Changing the seed is an experimental change, not a way to search for a better test score. Do not tune seed, threshold, model settings, features, or corpus selection using holdout results. All current documents appeared in earlier project experiments; this is independent of the current fit, not a historically untouched benchmark. Regenerating membership after dataset changes also does not undo prior exposure. External membership in the frozen public encoder's original pretraining is unknown.

## Training and validation

1. Load, clean, group, and assign roles. These deterministic text operations fit no model.
2. Build reference passage vectors, features, character vocabulary, reference statistics, and normalization using development documents only.
3. Use nested stratified group cross-validation on development data. Outer test groups are excluded from reference building, fitting, inner model selection, and calibration. Inner groups are disjoint and generate out-of-fold margins. Choose logistic regression or LightGBM separately inside each outer training fold from inner validation AUROC, retaining the fixed 0.02 improvement requirement for LightGBM. Fit each outer calibrator on inner out-of-fold margins only.
4. Report pooled outer predictions of that nested model-selection procedure. Compare candidate models on development folds to choose the final model; these candidate comparison metrics share final model selection and are labeled accordingly.
5. Fit the final verifier on development data only, calibrating with development out-of-fold margins. Report training-fit predictions as an optimistic diagnostic, with each candidate's own document omitted from its reference comparison.
6. Predict the sealed mixed-class holdout after final selection/fitting. Do not fit anything from these predictions. Generate the HTML report and save the manifest, evaluation, and trained artifacts.

The existing fixed small-model MVP remains: one frozen LUAR encoder, stylometry, character ngrams, logistic regression and optional LightGBM. Group-aware nested validation protects against document, copied-prose, and known negative-author overlap; it does not guarantee absence of overfitting. Three folds (or a valid two-fold fallback for small group counts) conserve sparse independent data. There is no broad hyperparameter search. Threads and chronological groups cannot be established from the supplied email filenames. Reference leave-one-document-out evaluation remains a separate development diagnostic.

The implementation follows [scikit-learn's grouped cross-validation guidance](https://scikit-learn.org/stable/modules/cross_validation.html) and [nested evaluation principles](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html). The final mixed holdout independently evaluates the current fitted model after development decisions.

## Usage and artifacts

```sh
python -m style_fingerprint build --seed 42 --holdout-fraction .2 --device cpu --offline
python -m style_fingerprint evaluate --json
# Explicit development-only diagnostic, without a mixed holdout:
python -m style_fingerprint build --no-holdout --artifacts artifacts/diagnostic --offline
```

```python
from style_fingerprint import StyleFingerprint
from style_fingerprint.config import Config
fp = StyleFingerprint.build('blog_posts', config=Config(seed=42), holdout_fraction=.2)
final_results = fp.evaluation['holdout']
```

Builds generate `artifacts/report.html` automatically. `evaluate` reruns development evaluation using saved role assignments and refreshes the report/artifacts. It does not resplit from changed files; rebuild to adopt source changes. Default builds require both classes on each side; `--no-holdout` / `holdout_fraction=0` deliberately preserves reference-only and small diagnostic workflows. The old `--primary-positive-tests` / `primary_test_dir` path is a legacy positive-only diagnostic and requires disabling the new holdout. It is not the current project evaluation policy.

The manifest's `documents`, `historical_document_ids`, `document_features`, saved passage table, and vector bank contain development data only. Separate `holdout_documents` snapshots retain raw/clean source text for reproducible later inference. Inclusion in that separate snapshot does not train the model. Candidate embeddings may be cached in memory but do not become reference vectors. All original files retain their bytes and locations; the previous three blog moves were reversed unchanged.

## Reading the HTML report

The standalone report uses no remote assets or scripts and opens directly in a browser. It shows:

- **Training fit:** accuracy, AUROC, average precision and Brier error on fitted development examples; explicitly optimistic.
- **Development cross-validation:** nested outer test predictions, with per-fold model selection and calibration confined to training groups.
- **Independent holdout:** AUROC, average precision, accuracy, positive acceptance, negative acceptance, Brier error, and confusion counts at fixed cutoff 50.
- **Holdout by source:** count, accuracy, positive acceptance for blog/work/Gmail, and negative acceptance (false acceptance) for negative_posts. AUROC is unavailable for single-class source subsets.

Metrics represent observed compatibility discrimination on these examples; 0–100 scores are not authorship probabilities. The report presents exact counts alongside rates. Small source subsets and mismatched negative genres remain major limitations. Neither repeated CV nor adding data proves improved generalization. Training and nested-development metrics cannot be substituted for final holdout results.

HTML contains aggregates only, without email bodies, excerpts, private filenames, or absolute source paths. The saved model artifacts and complete JSON evaluation contain source identities and private raw snapshots; keep them private under ignored `artifacts/`. Public documentation summaries contain aggregate results and public blog roles only; they do not enumerate private email identities. See [development](development.md) for concise verification. Generated evidence and metrics stay in ignored artifacts.

