---
source_type: ai_synthetic
human_authored: false
author_id: synthetic-lineage-adc9ead432422b41b0a5
synthetic_lineage_id: synthetic-lineage-adc9ead432422b41b0a5
synthetic_parent_id: adc9ead432422b41b0a5dac2
synthetic_parent_sha256: 94f42c7479a60b15ee9821210ef09bbd7cfba68f682cc3634fda7b85b12c9763
lineage_visibility: tracked
generator_id: agent-8
generation_attempt: 2
---

A download is not finished when the server responds

The public archive's export form was enough to retrieve my article list, but it took a few adjustments to make the process reliable. I used the browser's request inspector to identify the submitted fields, then wrote a small client with the same payload structure. Session-specific cookies stayed out of the saved configuration.

Submitting the entire list at once was a mistake. The server timed out before producing a complete response. Batches of twenty-five articles finished consistently, and a manifest let the script skip batches already on disk. A failed request now gets a delayed retry rather than an immediate loop of identical requests.

The exported envelope and the article content require different parsers. XML parsing extracts the title, revision reference, and body. A markup cleaner then converts the body into prose. At first I assumed that the cleaner's document wrappers were XML too. They were only text delimiters, so feeding them into an XML reader created errors that had nothing to do with the original download.

I replaced that second parser with a line-oriented reader based on the cleaner's documented boundaries. It emits a single document record at a time. This keeps memory use roughly tied to the largest article instead of the size of the whole collection.

The output includes a title, source reference, and cleaned text. Rejected records have a reason: empty body, missing boundary, or unsupported content. I also keep a small sample for manual inspection. A cleanly parsed record can still contain a navigation menu instead of an article.

Next I will compare document lengths across languages and inspect repeated text. Those checks should give us a useful foundation for the first classifier experiment.
