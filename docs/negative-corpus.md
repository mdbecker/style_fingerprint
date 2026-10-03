# Negative source collection and licensing

The active negative corpus admits only human-authored other-author email bodies and technical AI/ML blog prose. PEPs, RFCs, standards, specifications, documentation, news, marketing, social snippets and generated prose are excluded. The maintained inventory preserves attribution for active blog excerpts and removed historical sources. Preserve [the attribution inventory](negative-inventory.md), [curated source inputs](negative_sources.json), each sample's YAML attribution, and `negative_posts/manifest.json`. These are source provenance, not generated model evaluation snapshots.

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

Replacing the corpus invalidates supervised evaluation and production state: rebuild views, reference banks, vocabulary, comparison features, verifier, calibration, thresholds and prediction/report artifacts. Reuse embeddings only for unchanged text with valid cache keys. Source type (`email` or `technical_blog`) supports diagnostics only; it never enters verifier predictors. Report negative documents, authors, median compatibility and false acceptance separately by category and split. Historical PEP-population metrics do not measure the same task.
