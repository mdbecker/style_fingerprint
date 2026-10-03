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

The training collection begins with article titles from a public encyclopedia. I wanted material in several languages with revision references, so a public export was a better fit than scraping arbitrary sites.

Choosing the pages

I combined twelve weeks of page-view records and ranked titles within each language. The collector retained the first 25,000 eligible articles, excluding redirects and repeated titles. Popular pages provide a convenient selection rule, although they do not guarantee a representative language sample. I saved the selected title list so later experiments can use the same collection.

A small export client

The export page accepts batches of titles. To understand the request, I submitted three titles manually and inspected the browser's network entry. That showed the field names and request method without requiring a framework for crawling links.

The resulting Python client has a timeout, a pause between requests, and a bounded retry policy. I initially tried much larger batches, which failed often enough to make progress difficult to track. Smaller batches are slower per article but easier to resume. Each response is saved under a batch number, and a manifest marks completed downloads.

Errors are kept separate from content. If the server returns a failure page, that page should never become a language example. I check the response before sending it to the parser and leave unresolved batches in a retry list.

Cleaning the contents

The export contains article metadata and wiki syntax. A markup cleaner removes most layout instructions, links, and templates. I then inspect samples from every language rather than assuming cleanup behaves equally well across them. Navigation-heavy pages and extremely short passages are rejected.

The cleaner's output has record delimiters but does not behave like fully valid XML. I wrote a narrow reader for those delimiters and treat the body as plain text. It yields one record at a time, containing the language label, title, revision reference, and cleaned passage.

Keeping revision information lets me trace an unexpected training example back to its origin. Keeping rejection counts lets me tell whether a language genuinely has fewer examples or whether the cleanup stage failed. Next I will examine document lengths and prepare a split that keeps material from the same article on one side.
