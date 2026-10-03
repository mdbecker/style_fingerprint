---
source_type: ai_synthetic
human_authored: false
author_id: synthetic-lineage-c5b7e04ce577c8e5e441
synthetic_lineage_id: synthetic-lineage-c5b7e04ce577c8e5e441
synthetic_parent_id: c5b7e04ce577c8e5e441be45
synthetic_parent_sha256: aa4c4a3056638bae1456194f5b57ce6a57a5815ea09c57a5326145c824ead3d2
lineage_visibility: tracked
generator_id: agent-3
generation_attempt: 1
---

The most revealing test email was only four lines long. The sender had written a greeting, a question, a proposed time, and a farewell. After conversion, the question and the proposed time appeared as a single word. Nothing crashed. The output was valid text. It was also wrong.

Boundary errors are easy to overlook in text preparation. Removing a formatting element can remove the only separation between two visible fragments. A line break can become an empty string; a table cell can lose its neighboring space. Tokenization then treats the damage as ordinary language and carries it into every later calculation.

A good extraction test therefore specifies relationships as well as characters. Words that were separated should remain separated. A heading should not fuse with its paragraph. A list should remain distinguishable from a continuous sentence when that distinction matters. Exact visual imitation is unnecessary, but the output should preserve enough structure to support its purpose.

Other tests examine what must disappear. Presentation rules, hidden tracking elements, and executable page content generally do not belong in a linguistic representation of a message. Their removal should not require loading remote resources. The body can be interpreted locally, within the same protected environment that holds the original correspondence.

Character handling deserves equal attention. Accents, apostrophes, non-Latin scripts, and symbols can expose errors concealed by simple English samples. A replacement character may indicate that decoding failed rather than that the sender used an unusual symbol. Recording that distinction gives reviewers a place to investigate.

The pipeline also needs a policy for uncertainty. If two body alternatives disagree sharply, selecting one without a trace makes later debugging difficult. Store which alternative was chosen and why. If extraction yields unexpectedly little text, flag the record rather than silently treating it as a legitimate empty message.

Our four-line example became a permanent fixture. It was too small to be impressive and too useful to discard. Every change to the cleaner had to preserve the question and the proposed time as distinct fragments. That little check protected a basic promise: the text presented to the model should still contain the message a reader would recognize.
