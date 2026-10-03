# Negative source collection and licensing

The active negative corpus admits human-authored other-author email bodies, technical AI/ML blog prose and manually reviewed blind-generated `ai_synthetic` prose. PEPs, RFCs, standards, specifications, documentation, news, marketing, social snippets and unreviewed synthetic prose are excluded. The maintained inventory preserves attribution for active blog excerpts and removed historical sources. Preserve [the attribution inventory](negative-inventory.md), [curated source inputs](negative_sources.json), each sample's YAML attribution, and `negative_posts/manifest.json`. These are source provenance, not generated model evaluation snapshots.

## Attribution and reuse

Jay Alammar article samples use CC-BY-NC-SA-4.0; Christopher Olah and Gabriel Goh article samples use CC-BY-4.0. Their article links, original dates, content-license evidence, pinned revisions, and hashes are retained in the inventory and sample metadata. Theme/template licenses were not treated as permission for article content. Respect attribution, noncommercial, and share-alike obligations where applicable when distributing samples; these licenses are separate from project code.

Removed historical Python proposals had individual explicit public-domain declarations in their source documents. They were formerly collected from `python/peps` revision `e449c7e446faec3ecf953e83fbe677b771bf5d7c`; provenance retains credited authors, pinned URLs, original-source SHA-256, excerpt SHA-256, and each declaration's evidence. Their prose is deleted from the active corpus and cannot contribute to training, references, evaluation or reporting. Retained attribution records are historical provenance only. Code/template licensing alone was insufficient. Credits identify document authors/owners, not proven sole authorship of every sentence across revisions. Original dates do not certify unchanged or pre-AI current text.

## Curated collection

The collector fetches only explicit curated source inputs. Historical public AI/ML article sources are listed in the maintained JSON; selected public technical email messages and raw monthly archive checksums are kept in ignored acquisition inventories. Email collection selects exact Message-IDs from bounded public SciPy-Dev mbox snapshots, never stitches threads or uses entire archives as independent documents. Builds never fetch writing automatically. Samples are deterministic contiguous sentence-complete prose, not paraphrases or generated negatives. Per-source lengths vary: original article samples target roughly 250–750 whitespace words; natural email bodies retain only newly authored prose. Model usable-word counts use a different tokenizer from sampling.

Extraction strips markup, navigation, code, quoted blocks, equations, email headers, reply quotations, signatures and boilerplate while preserving prose paragraphs. Samples retain author and stable author identity, title, date, article/raw-source URLs, source repository/revision/path, license evidence, retrieval timestamp, sampling rule, counts, and hashes. Attribution metadata is not model prose. Credited identities group authors consistently in split/evaluation.

```sh
python scripts/collect_negative_corpus.py
python scripts/collect_negative_corpus.py --sources artifacts/negative_collection/email/sources.json --output artifacts/recollected-negatives
python -m style_fingerprint build --device cpu --offline
```

Downloaded article bodies, email bodies and raw archive/HTML snapshots are local training inputs, excluded by `.gitignore`. Public availability is recorded separately from permission to redistribute: preserve factual copyright/license metadata, and do not replace unknown terms with a permissive license. Existing public licensed samples remain attributed. The local manifest records current document/author counts; maintained docs do not freeze corpus totals. Whole selected authored emails retain natural message boundaries; code lines, quotations, signatures and boilerplate are removed before feature extraction.

The collector defaults to `docs/negative_sources.json`, requires explicit source-license information, and verifies pinned source/excerpt provenance. Keep attribution and licenses when recollecting or redistributing. Check collector help for overwrite and source-list options before changing existing samples.

## Evaluation limits

Choose realistic alternative writers with similar domain, genre and audience. Prefer older material reasonably believed to be human-authored, without introducing an AI-content detector. Author diversity matters more than raw document count; aim for 15–30 relevant authors and several documents each where available. Easy formal genres can inflate apparent performance without measuring personal style. Topic, length, formatting, and genre can discriminate labels without establishing authorship. Duplicate prose does not count as additional independent data. Known authors and copied-prose groups stay disjoint between development and final holdout; see [evaluation](evaluation.md). Supervision requires at least ten independent negative documents and, when reliable author metadata exists, at least three distinct negative authors. Fewer known authors keeps supervision disabled; unknown authors retain root-level grouping limitations. Exact identities and generated metrics remain in local ignored artifacts; only public source attribution belongs in maintained docs.

Replacing the corpus invalidates supervised evaluation and production state: rebuild views, reference banks, vocabulary, comparison features, verifier, calibration, thresholds and prediction/report artifacts. Reuse embeddings only for unchanged text with valid cache keys. Source type (`email`, `technical_blog` or `ai_synthetic`) supports diagnostics only; it never enters verifier predictors. Report negative documents, authors, median compatibility and false acceptance separately by category and split. Historical PEP-population metrics do not measure the same task.

## Blind synthetic curation

Use the maintained [synthetic generation guide](synthetic-generation.md) for source selection, isolated subagent prompts, full-output review, neutral retries, decision recording, batch closure, and retraining. It is an operational guide for future batches, separate from collection and licensing policy. Generators must never receive either guide or the reviewer-only catalog below.

Only manually reviewed `ai_synthetic` prose enters the negative corpus. Review source fit first—medium, audience, communicative purpose, and specificity—then require a clear contextual signal from T01–T30. The helper requires local fit evidence and valid labels, but does not judge their semantic correctness. Approval additionally requires 150–700 usable words, no copied twelve-word sequence or exact long source sentence, unchanged provenance, and the lineage cap. Synthetic examples augment real other-author negatives; real authored inputs remain positives.

Visibility is transitive: complete tracked ancestry permits `negative_posts/ai/tracked/`; any private or untracked ancestor permanently forces ignored `negative_posts/ai/untracked/`. All descendants of an original positive root share `author_id = synthetic_lineage_id = synthetic-lineage-<opaque id>`, so correlated rewrites remain grouped. Generating identity is diagnostic only. Source identifiers, excerpts, hashes, reviewer labels, and local review databases must not be published or used as verifier predictors.

The initial MVP gate requires at least one hundred approvals, at least three generators contributing twenty each with none above half the set, at least five original lineages, no more than twenty approvals per lineage, and twelve signal families. Larger batch targets and storage quotas require explicit checks beyond `status.complete`. Finish generation and review before reevaluation and production rebuilding. Report human and synthetic negatives separately; review-selected stylistic patterns are neither authorship probability nor proof of AI generation.

## Manual review catalog

A reviewer must judge a clear pattern in context; a single incidental phrase does not require acceptance. These labels must never be supplied to generators.

| ID | Observable family |
| --- | --- |
| T01 | Academic or LLM-favored vocabulary |
| T02 | Inflated evaluative vocabulary |
| T03 | Corrective not X, but Y framing |
| T04 | Not just, simply or merely framing |
| T05 | Less X / more Y or more than X framing |
| T06 | Tradeoff avoidance, such as without sacrificing |
| T07 | Explicit importance signalling |
| T08 | Formulaic transitions |
| T09 | Throat-clearing opener |
| T10 | Formulaic conclusion or call to action |
| T11 | Defensive or formal hedging |
| T12 | Faux balance or concession neutralization |
| T13 | Initial or trailing participial clauses |
| T14 | Nominalization and noun-heavy prose |
| T15 | Heavy phrasal coordination |
| T16 | Repeated rule-of-three constructions |
| T17 | Repeated parallel sentence structures |
| T18 | Low sentence or syntactic variability |
| T19 | Consistently elevated lexical sophistication |
| T20 | Distinctive repeated punctuation profile |
| T21 | Mechanically over-structured exposition |
| T22 | Persistently low informality or overly polished register |
| T23 | Mannered ornamental prose |
| T24 | Unsupported positivity or praise bias |
| T25 | Vague rhetorical padding |
| T26 | Semantic restatement or redundancy |
| T27 | Artificial rhetorical completeness |
| T28 | Generic stakeholder or generalization language |
| T29 | Inflated abstract metaphors |
| T30 | Repeated importance or consequence paragraph closures |
