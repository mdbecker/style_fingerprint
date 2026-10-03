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

Before a machine can read an inbox, someone must decide what counts as a message. The answer seems obvious until a reply contains a quoted thread, a promotional banner, an attached invoice, and two versions of the body that disagree.

A text pipeline should make that decision visible. Select the relevant body parts according to a documented policy. Decode their content using the message's encoding information. Treat attachments separately unless the analysis explicitly requires them. An attachment's filename is not prose simply because it appears near prose.

Plain text alternatives are convenient, but convenience should not exempt them from checks. An empty alternative may sit beside a complete HTML body. A short notice may refer the reader to content available only in the richer version. Selection rules should accommodate these cases without arbitrarily combining duplicate content.

For HTML, a tolerant parser can help recover a usable structure from imperfect input. Structure then guides extraction. Paragraphs need boundaries, inline formatting should usually preserve word continuity, and hidden styling instructions do not belong in the visible text. Character entities need interpretation rather than deletion.

Quoted replies present a separate policy question. For conversation analysis, retaining the earlier exchange may be useful. For classifying a newly authored reply, repeated history can dominate the result. Keep this filtering separate from HTML conversion so that a change in one policy does not silently alter the other.

Create a small suite of artificial messages that demonstrate intended behavior. Include non-English characters, mixed alternatives, nested markup, and a deliberately malformed body. Check the actual output, including whitespace. Tokenizers make distinctions based on those boundaries, and a single missing space can manufacture an unfamiliar term.

A large corpus can reveal additional patterns, but it should not become an excuse to inspect private content indiscriminately. Aggregate diagnostics and carefully controlled examples often expose systematic problems without unnecessary disclosure.

The quality measure is fidelity to the chosen purpose. Some pipelines need all visible content. Others need only the newest authored portion. Either can be defensible if the selection is explicit, its failures are observable, and later users understand which version of the message they received.
