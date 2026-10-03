---
source_type: ai_synthetic
human_authored: false
author_id: synthetic-lineage-adc9ead432422b41b0a5
synthetic_lineage_id: synthetic-lineage-adc9ead432422b41b0a5
synthetic_parent_id: adc9ead432422b41b0a5dac2
synthetic_parent_sha256: 94f42c7479a60b15ee9821210ef09bbd7cfba68f682cc3634fda7b85b12c9763
lineage_visibility: tracked
generator_id: agent-9
generation_attempt: 2
---

Reproducing the download request

The browser's developer tools helped me understand the export form. I submitted a small request, inspected the network entry, and copied its request details. That gave me a reference for the URL, method, and form fields; I did not need to guess which visible controls were actually sent.

I then replaced the browser-specific pieces with a small Python client. The client submits a list of article titles and saves the response before doing any parsing. Keeping that raw response made debugging much easier. An error in my cleanup code no longer required another download.

Large exports were unreliable, so I divided the title list into batches of forty. Each successful batch receives its own file, and a manifest records which titles it contains. Failed requests retry after a pause, with a limit on the number of attempts. A batch that still fails is logged for a later run rather than silently omitted.

Turning pages into training examples

The export includes metadata and text in wiki markup. For language classification, headings, templates, and link syntax are mostly unwanted features. I used an existing markup cleaner, then inspected a small sample from every language. This caught a few pages whose visible content was dominated by tables or navigation.

The cleaner's wrapper format looked like XML but did not consistently escape special characters. Instead of passing it to an XML parser, I read its documented record delimiters and treated the body as text. Each yielded record contains a title, revision reference, language label, and cleaned passage. The reader releases the preceding record before loading the next, keeping memory use predictable.

I also retained a rejection count for empty and exceptionally short pages. Otherwise it would be difficult to distinguish a small source collection from a broken cleanup step.

The next post will inspect the resulting corpus: document lengths, character distributions, and an initial train/test split. That should tell us whether the collection is suitable before we start comparing classifiers.
