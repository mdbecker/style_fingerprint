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

Before training the language classifier

The service we are building assigns incoming support messages to language-specific queues. A model that works in a notebook is only one part of that service. We will also need a repeatable build, predictable response time, and a way to replace the model without interrupting intake. This article covers the earlier dependency: acquiring text that can support a meaningful experiment.

I started with public encyclopedia material because it offers long passages in several languages under a consistent export structure. Popularity statistics helped narrow the candidate pages, but I did not use popularity as a quality label. A heavily visited page can be mostly a table, a redirect, or a short disambiguation notice.

For this prototype I selected eighteen thousand candidate titles in each of nine languages. The selection spans ten weeks of traffic. Namespace filters remove user discussions and maintenance pages. Keeping the editions separate avoids letting English volume dictate the sample size everywhere else.

A modest downloader

The export form can fetch multiple titles in one request. I inspected a successful submission, reproduced its payload with a small Python client, and stored the raw response before doing any cleaning. The client sends batches of thirty, waits between requests, and records failed batches. This is a download job with a known list of inputs; a general-purpose spider would add little value.

Raw storage matters. When I adjusted the cleaner, I could rerun it against the same responses instead of asking the remote server for another copy. Each accepted record also retains a revision reference for tracing extraction errors.

Cleaning boundaries

The response is XML, but the article body contains encyclopedia markup. I parse the export first and pass only the body through a markup cleaner. Navigation templates and link syntax should disappear; accented characters and normal punctuation should remain. Short spot checks caught a cleaner setting that was removing entire parenthetical phrases.

The final records are plain text plus language and provenance fields. They are not yet a finished training set. In the next post I will look at duplicates, very short records, and the mismatch between encyclopedia paragraphs and brief support messages. Those checks determine whether the classifier has learned language rather than quirks of the collection process.
