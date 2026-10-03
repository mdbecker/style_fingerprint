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

Building a small multilingual corpus

For the language router, I needed ordinary prose rather than a collection of translated example sentences. Public encyclopedia exports gave me a workable starting point. I first summed daily article traffic across twelve weeks, keeping the ranking separate for each language. That prevented the largest edition from swallowing the entire sample.

The selection script retained twenty thousand titles per edition. Redirects and obvious administrative pages came out before download. I saved the selection list with the acquisition date so another run could use the same inputs even if the popularity rankings changed.

Retrieving the pages

A full crawler would have introduced more machinery than this job needed. The export endpoint already accepted a list of titles, so I built a short HTTP client around it. Inspecting one successful browser submission revealed the field names and encoding. I then reproduced that request with an explicit timeout and a descriptive user agent.

The first large submission failed. Smaller batches of forty titles proved much more reliable. Each batch goes into its own file, and a manifest records whether it completed. If the network drops halfway through, the next run resumes from the manifest rather than downloading everything again. Retries wait progressively longer; repeated failures remain visible for later inspection.

Producing usable text

The downloaded records include revision metadata and markup. A markup converter handles headings, links, and templates; a streaming XML reader handles the outer export. Those are separate jobs. Treating the converter's output as valid XML caused avoidable parsing errors during my initial experiment.

For each accepted page, I keep its title, language, revision reference, and cleaned body. The reader yields one record at a time, which lets the cleaning stage work on a laptop without retaining the whole corpus in memory. Empty bodies and pages consisting mostly of lists go into a rejection counter.

The next installment will examine document lengths and duplicated passages before any classifier is trained. Acquisition success is easy to measure. Whether these pages resemble the messages the router will actually receive is the more useful question.
