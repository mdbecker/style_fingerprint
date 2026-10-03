---
source_type: ai_synthetic
human_authored: false
author_id: synthetic-lineage-c5b7e04ce577c8e5e441
synthetic_lineage_id: synthetic-lineage-c5b7e04ce577c8e5e441
synthetic_parent_id: c5b7e04ce577c8e5e441be45
synthetic_parent_sha256: aa4c4a3056638bae1456194f5b57ce6a57a5815ea09c57a5326145c824ead3d2
lineage_visibility: tracked
generator_id: agent-1
generation_attempt: 1
---

The complaint was beautifully specific: the search system could find the word green, but not greenhouse. Both appeared in the same email. Somewhere between delivery and indexing, the longer word had become green house.

This was not a search problem. It was an extraction problem disguised by a successful pipeline. Every stage had completed without raising an exception, and the dashboard was entirely satisfied.

Email offers many opportunities for this kind of quiet damage. A sender can put formatting tags inside a word. A table can arrange fragments in a reading order that differs from their order in the file. A message can include a plain text alternative that omits the main content. Transport encodings can conceal characters until they are decoded correctly.

Testing the extractor requires examples designed around these possibilities. A synthetic message is often more useful than a large anonymous sample because its expected meaning is known. Put emphasis inside a word. Use an entity for a character. Include nested quotations, a misleading attachment name, and a multipart body with one empty alternative.

The expected output should reflect the analysis's purpose. Search may need preserved word boundaries and paragraph order. Sentiment analysis may be harmed by quoted text from a previous correspondent. A language classifier may need accented characters that a search normalizer would happily simplify. There is no universal clean text independent of use.

Separate the transformations. First select and decode the relevant message part. Then extract visible text. Then apply optional policies for quotations, signatures, and normalization. If one combined function performs everything, a change intended to remove a footer can unexpectedly change how malformed markup is handled.

Keep track of failures that produce text as well as failures that produce nothing. A document reduced to navigation labels is not an extraction success. Neither is a reply dominated by years of forwarded correspondence.

When the greenhouse test finally passed, the team added a nearby case with two genuine words separated by a line break. Fixing one boundary should not erase another. The extractor had become a little less confident and considerably more trustworthy.
