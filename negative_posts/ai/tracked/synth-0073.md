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

The extractor produced a blank document from a message that looked perfectly readable in the mail client. The developer's first reaction was to change libraries. Her second, more productive reaction was to save a tiny example that demonstrated the failure.

The example showed why visual confidence is a poor guide to document structure. A mail client may repair malformed markup in one way, while a parser repairs it in another. Both can operate as designed and produce different interpretations. The extraction process needs tests tied to its own intended result.

Begin with the outer message representation. Encoded bytes must become characters before an HTML parser sees them. The body must be selected from the message's parts, with duplicate alternatives handled deliberately. If these steps are wrong, switching the HTML parser may merely change the appearance of the damage.

Next, consider how text boundaries are created. Block elements commonly imply separation, while inline elements may divide a word only for styling. Removing all tags and inserting a space for every removal can distort both cases. Conversely, concatenating everything can merge headings, paragraphs, and table cells.

Discard content that is not intended as visible prose, such as style rules and executable scripts. Decide how to handle image descriptions and link text according to the analysis. A promotional footer might be visible but irrelevant; its removal belongs to a later filtering policy rather than a universal definition of HTML conversion.

The developer added examples for nested tags, entities, broken nesting, and an empty plain text alternative. She checked the output strings rather than counting successful parses. A parser that returns something has satisfied only a mechanical requirement.

She also separated extraction from signature and quotation removal. Those operations involve different assumptions and deserve different tests. A false signature boundary can erase a short reply completely, which is a different failure from malformed markup.

The final fix was modest. It changed one selection rule and made paragraph handling explicit. The library stayed. More valuable than the fix was the collection of examples: future changes would now have to explain their behavior on the cases that had once been invisible.
