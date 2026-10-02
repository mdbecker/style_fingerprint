# One combined positive dataset

Positive source handling follows the current specification. Blogs, work emails, and Gmail documents all belong to **one positive class with equal document weight across sources**. There is one fingerprint and one verifier, with no source-specific models, separate training populations, or source weighting. Source labels remain provenance and diagnostic fields only.

The current [seeded mixed holdout](evaluation.md) supersedes the previous separate positive-only test directory. All sources remain one positive class, but holdout documents are excluded from that training class.

| Input | Development | Holdout | Available |
|---|---:|---:|---:|
| blog_posts | 3 | 3 | 6 |
| work_corpus | 36 | 9 | 45 |
| gmail_corpus | 14 | 4 | 18 |
| **Positives** | **53** | **16** | **69** |
| negative_posts | 80 | 20 | 100 |

All 69 cleaned bodies are distinct. The 100 real negative source excerpts are also distinct and do not exactly match a positive body. Negative count therefore exceeds positive count, without counting chunks as independent examples. Of the 100 negatives, 57 have fewer than 150 usable words; their varied lengths reduce the obvious short-email/long-article contrast, but do not eliminate genre confounding. The examples are independently sourced writing by other people, not synthetic prose.

## Build and use

Normal builds discover sibling `work_corpus/` and `gmail_corpus/` beside the blog directory. Plain-text message discovery is recursive and case-insensitive. Existing work and blog identities remain stable; Gmail IDs use `gmail/<relative-path>`. Email originals are not moved, renamed, or rewritten. All six unchanged blog originals are under blog_posts; seeded roles are recorded in the manifest. The manifest records both email roots, counts per source, raw/clean text, source hashes, `dataset_counts`, and `positive_training_policy`.

```sh
python -m style_fingerprint build --device cpu --offline
python -m style_fingerprint score new-email.txt --input-format email
python -m style_fingerprint explain new-email.txt --input-format email
python -m style_fingerprint evaluate --json
# Explicit roots:
python -m style_fingerprint build --work-corpus work_corpus --gmail-corpus gmail_corpus --offline
# Preserve the combined bank while building a blog-only diagnostic:
python -m style_fingerprint build --no-work-corpus --no-gmail-corpus --artifacts artifacts/blog-only --offline
```

```python
from style_fingerprint import StyleFingerprint
fp = StyleFingerprint.build('blog_posts', work_dir='work_corpus', gmail_dir='gmail_corpus')
result = fp.score(email_text, input_format='email')
# None discovers a sibling directory; False disables that source:
blog_only = StyleFingerprint.build('blog_posts', 'artifacts/blog-only', work_dir=False, gmail_dir=False)
```

An explicit missing/empty email directory fails clearly. Loading uses the persisted snapshot; rebuild when inputs change. Offline mode requires the cached pinned checkpoint. The main pretrained encoder, 95 features, character signal, passage rules, grouped holdouts, and small verifier selection remain the MVP architecture.

## Cleaning and identity

Gmail uses the same plain-text cleaner as work emails, with `gmail_email` recording the input source. That label is not a claim that every export is an email: one supplied file contains a longer presentation transcript, which remains a user-authored positive document. A tests-first cleaning fix limits author-name signature removal to a short trailing block (at most 80 words). An author credit near the beginning of a long document no longer discards its body. Standard signature separators, clear reply boundaries, quoted lines, image placeholders, exported headers, URLs, and email addresses retain their previous handling. Indented prose and underscores remain intact. See [email cleaning details](corpus.md).

Plain-text cleaning cannot reliably separate inline quotations, unmarked source code, template content, and other people's contributions. Review those cases in originals. Send dates and conversation identity are not inferred from filenames or file timestamps. Separate documents may still come from related conversations; no thread-disjoint or chronological validation claim is made.

## Training and negatives

Every positive document contributes the same weight within the positive class, including the smaller blog source. Logistic regression retains its pre-existing positive/negative class balancing. Sigmoid calibration gives each class total weight one, with equal per-document weights within each class and no source-dependent adjustment. The legacy calibration metadata argument remains accepted but has no weighting effect. Source summary fields exist to diagnose confounding and do not split the dataset.

At least ten distinct negatives and six distinct positives enable nested supervised validation. The previous requirement for three credited negative authors is removed under the user's latest instruction: other authorship is sufficient for membership. When three or more author identities are known, author holdouts remain a useful evaluation safeguard. With fewer, the model uses whole-document holdouts and records `negative_grouping: document`, warning that unseen-author generalization cannot be established. Grouping is an evaluation strategy, not a negative eligibility restriction. The current corpus has 60 credited author identities and uses author-grouped negatives. Positive documents are held out as entire documents, with training-only references/calibration and existing duplicate-prose filtering.

A warning now reports independent negative scarcity relative to positives. It does not fabricate examples or crawl the web. Additions are explicit in [negative_sources.json](negative_sources.json), and collection is reproducible from pinned raw repository URLs. The 88 added Python proposals each carry an explicit public-domain declaration in their own source; they are not covered merely by a code/template license. Header metadata, indented code/quotes, directives, references, and copyright text are removed before excerpting. The collector now supports reStructuredText and explicit minimum/maximum sample lengths. [Full negative inventory](negative-inventory.md) lists every source, credited author, date, length, and license.

## Limits and local handling

Pooling sparse sources increases available positive data; it does not establish improved accuracy. The positive pool remains mostly email, while negatives remain technical articles/proposals. Topics, length, formatting, and editorial differences can still explain discrimination. PEP credits identify document authors/owners, not a verified sole author of every sentence across all revisions. Original publication dates also do not certify unchanged or pre-AI current text. The 0–100 result remains compatibility rather than an authorship probability. Reported grouped metrics share model-selection validation, so they are exploratory.

Both `/work_corpus/` and `/gmail_corpus/` are ignored by Git, along with artifacts and model caches. Source originals, raw persisted text, and explanations/analogues can contain private material. The ignore rules do not remove already tracked files, and custom private directories need equivalent exclusion. Tests use invented prose; documentation contains aggregate counts and public negative metadata only. Inference remains local with the cached pretrained checkpoint.


## Authorship and cleaning

The supplied messages are assumed to contain prose authored by the user. Both email loaders default to the user's public author identity; source metadata distinguishes `work_email` from `gmail_email`. Optional YAML front matter can supply author metadata; work genre is fixed by the source loader. Publication/send dates are not inferred from file timestamps. A filename is a document ID, not a verified conversation/thread ID.

Email cleaning preserves greetings, authored closings, prose, punctuation, contractions, paragraph breaks, and underscores. It recognizes leading exported headers, `>` quoted lines, standard `On … wrote:` reply boundaries, original/forwarded-message separators, signature separators, author-name signatures followed by recognizable role/contact lines, URLs/email addresses, and standalone `Image` placeholders. Common Outlook bullet markers are normalized. Indented prose is preserved rather than interpreted as a Markdown code block. Cleaned email prose supplies structural features too, so stripped quotations/signatures cannot reappear through feature extraction.

This is conservative plain-text cleaning, not a complete mail parser or de-identification system. Review atypical signatures, inline quotations, boilerplate, and text written by other people. Only clear boundaries are removed; normal authored greetings and sign-offs remain. Raw originals and raw artifact text are retained locally for provenance.


Private artifacts may contain complete raw messages and source identities. Keep both private input trees and generated outputs ignored. Publish only aggregate descriptions, never individual private filenames or IDs.
