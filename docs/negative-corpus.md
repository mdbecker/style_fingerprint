# Negative source collection and licensing

The maintained inventory contains 100 distinct real other-author excerpts: 12 AI/ML articles and 88 Python proposals. Preserve [the attribution inventory](negative-inventory.md), [curated source inputs](negative_sources.json), each sample's YAML attribution, and `negative_posts/manifest.json`. These are source provenance, not generated model evaluation snapshots.

## Attribution and reuse

Ten Jay Alammar article samples use CC-BY-NC-SA-4.0; Christopher Olah and Gabriel Goh contribute one article each under CC-BY-4.0. Their article links, original dates, content-license evidence, pinned revisions, and hashes are retained in the inventory and sample metadata. Theme/template licenses were not treated as permission for article content. Respect attribution, noncommercial, and share-alike obligations where applicable when distributing samples; these licenses are separate from project code.

The 88 added Python proposals have individual explicit public-domain declarations in their source documents. They were collected from `python/peps` revision `e449c7e446faec3ecf953e83fbe677b771bf5d7c`; provenance retains credited authors, pinned URLs, original-source SHA-256, excerpt SHA-256, and each declaration's evidence. Code/template licensing alone was insufficient. Credits identify document authors/owners, not proven sole authorship of every sentence across revisions. Original dates do not certify unchanged or pre-AI current text.

## Curated collection

The collector fetches only the explicit maintained input list. Builds never fetch writing automatically. Samples are deterministic contiguous sentence-complete prose, not paraphrases or generated negatives. Per-source lengths vary: original article samples target roughly 250–750 whitespace words; shorter proposal samples use explicit per-source minimum/maximum targets to reduce a simple short-email/long-article contrast. Model usable-word counts use a different tokenizer from sampling.

Extraction strips markup, navigation, code, quoted blocks, equations, reStructuredText headers/directives/references, and copyright appendices while preserving prose paragraphs. Samples retain author and stable author identity, title, date, article/raw-source URLs, source repository/revision/path, license evidence, retrieval timestamp, sampling rule, counts, and hashes. Attribution metadata is not model prose. Credited identities group authors consistently in split/evaluation.

```sh
python scripts/collect_negative_corpus.py
python -m style_fingerprint build --device cpu --offline
```

The collector defaults to `docs/negative_sources.json`, requires explicit source-license information, and verifies pinned source/excerpt provenance. Keep attribution and licenses when recollecting or redistributing. Check collector help for overwrite and source-list options before changing existing samples.

## Evaluation limits

There are 60 credited negative identities across the complete current inventory. Technical articles/proposals remain a different distribution from many positive emails, even with variable sample lengths. Topic, length, formatting, and genre can discriminate labels without establishing authorship. Duplicate prose does not count as additional independent data. Known authors and copied-prose groups stay disjoint between development and final holdout; see [evaluation](evaluation.md). Negative eligibility requires other authorship, not a minimum number of credited authors. Exact identities and generated metrics remain in local ignored artifacts; only public source attribution belongs in maintained docs.
