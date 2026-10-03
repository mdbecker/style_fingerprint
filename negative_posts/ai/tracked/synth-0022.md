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

Building a language corpus without a large crawler

The collection script began with a list of public encyclopedia pages grouped by language. I ranked candidates using aggregated readership data, then sampled from several popularity ranges. The goal was ordinary prose with enough topical variety to make a useful training set.

Fetching the text did not require a general-purpose crawler. There was a known endpoint and a finite list of page identifiers. I used a small client that sends a batch, writes the response to disk, and records success before moving on. When a batch fails, it remains in the pending list rather than disappearing into a console log.

Inspecting one browser request helped establish the parameter names. I then removed session-specific headers and made the request configuration explicit. An unattended script should not depend on an old browser cookie accidentally surviving.

Large batches proved unreliable, so the client limits each request to forty pages and backs off after a temporary server error. That limit is a collection setting, not part of the statistical model.

The exports contain markup as well as prose. I run a cleanup pass, inspect a sample from every language, and discard pages that contain little usable text. The parser yields a document at a time and writes plain paragraphs alongside a separate revision manifest. That keeps memory use predictable and lets me trace a suspicious example back to its public revision.

Next I will compare document lengths and character distributions before fitting a baseline. If cleaning leaves language-specific formatting behind, the classifier may learn the export process instead of the language.
