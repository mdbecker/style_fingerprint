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

From browser export to document stream

A successful browser request gave me the specification I needed for the archive downloader. I noted the form fields and encoding, then built a client that submits the same kind of request with a known list of titles. I did not retain personal session cookies or copy every browser header indiscriminately.

The initial batch contained several hundred titles and failed repeatedly. Reducing it to thirty made the requests predictable. Each response is saved before extraction, and a small status file lets the next run resume unfinished work. Transient failures receive a delayed retry; permanent failures are reported separately.

The response includes an XML envelope and bodies written in wiki markup. These require two operations. First, the XML reader extracts the article and revision metadata. Second, the markup converter removes link syntax, navigation templates, and formatting instructions. Mixing those operations made the first implementation harder to debug.

The converter surrounds each document with its own text markers. Those markers look like XML but do not obey XML rules. I replaced the second XML parser with a reader that recognizes the converter's boundaries. It yields one dictionary for each article, containing a title, revision reference, and plain body text.

Yielding records also avoids holding the full export in memory. The writer can process a document, save it, and move on. Peak usage now depends largely on the largest document being cleaned.

I inspect a small sample from every batch, particularly articles with tables or unusual templates. Parsing without an exception is not proof that the content is useful. Next I will compare extraction quality and document lengths before using this material to train a language detector.
