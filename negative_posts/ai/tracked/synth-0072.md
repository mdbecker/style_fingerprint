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

Before a language classifier can sit behind an application, it needs a training collection we can explain and reproduce. This post describes the collection step for the model in my demo, which routes incoming text to language-specific processing workers.

Selecting articles

I used a public encyclopedia because it offers substantial text in several languages and preserves revision information. Popularity was a starting point for choosing pages, rather than a claim that popular pages represent every kind of writing. I aggregated three months of page-view records and selected up to 30,000 titles per language. Redirects and duplicate titles were resolved before downloading.

The title list is saved separately from the article content. That gives the experiment a stable input inventory even if the site's popularity rankings change later. It also makes omissions visible instead of allowing failed downloads to disappear into a smaller dataset.

Downloading in batches

For the export request, I first inspected a successful submission in the browser's network panel. The useful information was the request method and the names of the form fields. I then wrote a small Python client with explicit timeouts and a limited retry policy.

A single large export frequently failed. Batches of fifty titles were more dependable, and each batch was written to disk before parsing. The downloader records completed batches so an interrupted run can continue. Errors go into a separate queue for review; they do not become empty training examples.

Removing markup

The exported text contains templates, links, and layout syntax. I passed it through a markup cleaner and inspected samples from each language. Tables and navigation-heavy pages were common sources of poor examples. Pages with little remaining prose were rejected, with the reason recorded.

For every retained article, I save the title, language, revision reference, and cleaned text. The record reader yields one article at a time. Downstream code can then sample or count documents without holding the entire collection in memory.

There are limits to this corpus. Encyclopedia prose is cleaner and longer than much of the text our service receives. After cleanup, I will examine length distributions and test shorter excerpts separately. The next step is an exploratory notebook, followed by a split that keeps fragments from the same article together.
