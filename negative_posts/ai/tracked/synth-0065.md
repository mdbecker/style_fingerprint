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

The text extractor returned a thousand words from an email that showed only two short paragraphs. Most of the extra material came from the machinery surrounding the message: style declarations, hidden navigation, and a generous footer repeated from earlier correspondence.

This is the point where a text pipeline needs an editorial policy. The software cannot infer the researcher's purpose from the presence of readable characters. A style rule contains words, but those words may have no relevance to the communication. A quotation contains communication, but it may belong to another author or another time.

Begin by separating representation from selection. Representation asks how to convert the chosen body into readable text. Selection asks which portions of that text belong in the dataset. Solving both with one sweeping rule makes it difficult to understand why a sentence vanished.

For representation, pay attention to structure. Decode characters correctly, preserve useful boundaries, and handle damaged markup without letting recovery become silent data loss. Check the output of the actual parser configuration being used. A library name alone does not specify its behavior on awkward input.

For selection, define categories that match the task. A study of reply language may remove quoted history; a study of conversation context may retain it with explicit boundaries. A routing classifier may benefit from subject lines, while an authorship study may need to treat them separately. These choices should be visible in both the documentation and the record schema.

Verification can remain compact. Maintain a set of invented examples that express the policy, and inspect representative real outcomes in a protected setting. Track indicators such as extraction length, empty output, and retained quote proportion where useful. Sudden changes in those indicators can reveal a regression before model scores do.

The aim is a corpus whose contents can be explained. If a reviewer asks why a fragment appears or disappears, the answer should refer to the purpose and the rule. “The parser happened to do that” is evidence about the software, not an adequate reason for the dataset.
