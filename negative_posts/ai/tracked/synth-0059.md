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

Fetching articles without building a crawler

The archive already provides an export form, so my downloader has a finite job: submit known titles and save the responses. I inspected a successful submission to identify the request method, field names, and character encoding. A small HTTP client was sufficient once those details were clear.

Large submissions were unreliable. I reduced the batch size to fifty titles and saved each response separately. The download manifest records completed batches, retry counts, and persistent failures. This makes an interrupted run recoverable and keeps a troublesome page from blocking the rest of the collection.

I added a short delay between requests and capped the number of retries. A client should not hammer a struggling server merely because it has more pages to collect. Responses are written to temporary files first and renamed only after the download completes.

Separating the formats

The export's outer structure is XML. Inside it, the body is encyclopedia markup. I use an XML reader to extract each page, then a markup library to produce readable text. Keeping these stages separate made error diagnosis much easier.

The cleaner emits document boundaries that resemble tags, but its output is not a general XML document. Rather than pretend otherwise, I read those documented boundaries explicitly. Each record contains the page title, revision reference, language, and body. The iterator returns records individually, allowing the next stage to write them without loading the entire file.

I checked samples containing accented text, links, tables, and nested templates. The first three behaved sensibly; complicated templates needed a rejection rule. Dropping a clearly broken extraction is preferable to training on navigation fragments mislabeled as prose.

The resulting corpus is now ready for inspection, not yet for modeling. My next post will examine repeated paragraphs, language balance, and unusually short documents. After those checks, I will establish a simple classifier baseline and see whether the collection supports the intended task.
