---
source_type: ai_synthetic
human_authored: false
author_id: synthetic-lineage-adc9ead432422b41b0a5
synthetic_lineage_id: synthetic-lineage-adc9ead432422b41b0a5
synthetic_parent_id: adc9ead432422b41b0a5dac2
synthetic_parent_sha256: 94f42c7479a60b15ee9821210ef09bbd7cfba68f682cc3634fda7b85b12c9763
lineage_visibility: tracked
generator_id: agent-7
generation_attempt: 2
---

Retrieving and cleaning the training pages

I had a list of public articles for our language classifier, but the list was not yet a dataset. Turning it into useful examples required two separate jobs: preserve the raw revisions, then extract prose from them.

For retrieval, I wrote a small request client instead of installing a general crawler. The input was a finite manifest, and the endpoint was already known. The client sends twenty-five revisions at a time and saves the entire response before advancing. Failed groups stay pending, with the error and attempt count recorded beside them.

A browser network trace helped establish the export parameters. I did not retain browser cookies or session headers in the script. That made the job repeatable on another machine and avoided relying on an interactive login.

The extraction pass removes the markup surrounding article paragraphs. Existing software handled much of that work, but its output needed a dedicated record reader. Treating it as ordinary XML produced errors because the wrapper syntax was only superficially similar.

My reader yields one document at a time and preserves the public revision reference separately. I also reject records that are mostly references, lists, or empty headings. A sample from each language goes into manual inspection, where I can compare the extracted text with the public page.

The next article will use those samples to examine length and character patterns. Before optimizing the classifier, I want evidence that it will learn language rather than a collection of accidental formatting clues.
