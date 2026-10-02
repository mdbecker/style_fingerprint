# Current MVP specification

This is the authoritative specification, consolidating the supplied addendum and later user requirements. [Repository instructions](../AGENTS.md) govern workflow and documentation. [Historical supplied specifications](historical-specifications.md) preserve provenance, not current requirements. Later explicit user instructions override this document.

## Product and architecture

Build a small local Python API and four-command CLI (`build`, `score`, `explain`, `evaluate`) that returns a 0–100 writing-style compatibility score, deterministic evidence strength, interpretable differences, passage/sentence sensitivity, and nearest historical passages. Never label the score an authorship probability, forensic proof, or AI-detection result.

Use exactly three signals: one frozen pretrained LUAR authorship encoder, 50–100 stable interpretable stylometric features (currently 95), and character 3–5 gram TF-IDF. Compare passage-vector sets with symmetric MaxSim cosine; do not average the corpus into a single vector. Normalize reference similarities with fixed weights 0.60 embedding, 0.25 stylometry, 0.15 character when supervision is inadequate.

Use small logistic regression and optional LightGBM over derived comparison features, never raw transformer dimensions. Select boosting only for a development AUROC improvement of at least 0.02. Supervision needs ten independent negatives and six independent development positives. Negative author count is not an eligibility restriction; preserve authorship and group known authors when possible. Calibration gives equal class mass and equal document weights within each class. Do not add another transformer, semantic control model, LLM judge, neural classifier, service, database, vector index, synthetic negatives, or transformer fine-tuning.

Keep plain functions and small dataclasses. The model checkpoint is pinned in configuration; cache by passage content/model revision/preprocessing/encoding version. Retain individual passage identities and clean-text offsets. Persist local manifest, passages, vectors, vocabulary, optional verifier, evaluation, and an HTML report in ignored artifacts. Fail clearly on unusable input, invalid groups, incompatible artifacts, or unavailable checkpoint. Offline builds require cached weights; loading uses persisted snapshots and lazy inference.

## Data and privacy

Discover Markdown recursively under blog inputs and plain-text messages recursively under both private email sources. Pool blogs, work emails, and Gmail into one positive class with equal document weight. Preserve originals. Remove markup/code/navigation from Markdown and recognizable exported headers, quoted replies, signatures, placeholders, URLs, and addresses from emails while preserving authored prose structure. Limit author-name signature removal to short trailing blocks; preserve long authored exports. Review unmarked quotations and mixed authorship manually.

Paragraph chunks target 300 words with no overlapping windows, merge short tails where possible, and split oversized text at sentence/word boundaries with a 700-word maximum. An entire short document remains scoreable; fewer than three usable words fails. LOW evidence is below 150 words, MEDIUM 150–499, HIGH at least 500; extreme component disagreement downgrades one level. Report five strongest feature matches and five mismatches, top three analogues per passage, at most three suspicious passages and twenty sentence-deletion checks. Explanations are deterministic measurements, not LLM judgments.

Use real other-author negatives with source attribution, licenses, pinned revisions, and hashes. Collection is explicit and curated; runtime builds do not crawl. Never publish private corpus text, filenames, IDs, or generated private artifacts. Fixtures must be invented; generic source labels and aggregate descriptions are permitted. See [corpus handling](corpus.md) and [negative licensing](negative-corpus.md).

## Independent evaluation

Before fitting, assign a reproducible mixed-class holdout using a configurable seed (default 42). Reserve at least half the blogs rounded up, and at least three when three exist. Other positive sources and negatives target 20%, rounded up. Both development and holdout require both labels; fail if independent groups cannot support the split, unless a development-only diagnostic explicitly disables holdout.

Keep negative-author groups and connected exact-body/substantial-paragraph duplicate groups together. Reject cross-label duplicate prose. Sort identities before seeded source-stratified group shuffling; save the inventory fingerprint, exact roles, and groups privately. Rebuild regenerates assignments; loading/evaluation preserves saved membership. Never select seed, features, thresholds, calibration, or model settings from holdout performance.

Use nested stratified group cross-validation on development data: inner validation chooses each outer-fold model and provides calibration margins; outer test groups stay excluded from fitted vocabulary, references, statistics, model choice, and calibration. Report nested selection metrics separately from candidate comparisons guiding final model choice. Fit the final model on development only, then predict the final holdout without further fitting.

Automatically generate standalone HTML showing optimistic training fit, development test predictions, independent holdout metrics/confusion counts, and holdout results by blog, work, Gmail, and negatives. Source-specific single-class subsets cannot have AUROC. Generated reports and metrics stay under ignored artifacts unless publication is explicitly requested. Prior exposure in earlier experiments, unknown encoder pretraining membership, sparse source subsets, related conversations, and genre/topic confounding limit independence and generalization claims. See [evaluation](evaluation.md).

## Development and documentation

BDD red → green → refactor is mandatory for each functionality stage. Write and run failing observable-behavior tests before implementation; investigate unexpected passes. Test ingestion, cleaning, chunking, scoring, evidence, explanations, retrieval, determinism, caches, persistence, errors, grouping/leakage prevention, optional supervision, report privacy, and documentation policy. Use pytest; no Gherkin framework is required. Mock only the external pretrained encoder boundary for fast tests; keep real CPU inference in opt-in integration tests.

Maintain documentation in place. Tests-first development does not require published run logs. Generated transcripts, intermediate snapshots, model reports, and privacy audits belong in ignored artifacts. Record concise verification in [development](development.md), preserve attribution, and run the explicit inventory/link checker before finishing.
