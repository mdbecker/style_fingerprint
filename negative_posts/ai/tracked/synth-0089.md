---
source_type: ai_synthetic
human_authored: false
author_id: synthetic-lineage-c5b7e04ce577c8e5e441
synthetic_lineage_id: synthetic-lineage-c5b7e04ce577c8e5e441
synthetic_parent_id: c5b7e04ce577c8e5e441be45
synthetic_parent_sha256: aa4c4a3056638bae1456194f5b57ce6a57a5815ea09c57a5326145c824ead3d2
lineage_visibility: tracked
generator_id: agent-2
generation_attempt: 1
---

The first extractor was judged by whether it removed the angle brackets. The second was judged by whether the remaining words still made sense. That change in the test transformed the project.

HTML email is a layout with language inside it. Stripping the layout can alter the language if the converter ignores the role of spacing, nesting, and hidden content. Two neighboring cells may need a separator. A hidden preview may repeat the opening sentence. A link may display useful words while carrying an address full of tracking parameters.

A good extraction policy handles these cases according to the intended analysis. For ordinary text classification, visible link labels may be more useful than destinations. For detecting suspicious links, destinations may be essential. One conversion cannot silently satisfy both purposes.

Plain text alternatives should also be inspected. Their existence does not guarantee completeness. Some are carefully written equivalents; others are minimal fallbacks. Prefer them under a rule that has been tested on the kinds of messages in the collection. Avoid combining alternatives unless there is a clear reason, since duplication can distort token counts.

Malformed input needs graceful handling, but grace should include visibility. If the converter repairs a damaged body, retain an indicator where practical. If it cannot recover meaningful content, record a failure rather than treating the result as a normal empty message. The distinction matters when calculating corpus statistics.

A compact test collection can express the desired behavior using invented messages. Include ordinary paragraphs, lists, tables, escaped characters, broken nesting, and repeated quote blocks. Every example should make a specific expectation clear. This prevents a later library change from redefining the corpus unnoticed.

The most valuable review is often side by side: what a person reads, and what the analysis receives. Differences will remain, but they should be purposeful. Once the extractor is judged by meaning rather than merely by removed markup, text preparation becomes a defensible part of the study instead of a hidden prelude.
