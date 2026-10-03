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

The archive looked clean until we searched it. A sentence visible in a mail client had vanished from the index. Another appeared twice. A third had acquired the name of an image file halfway through its opening clause. The extractor had completed without an error, which proved to be a remarkably weak definition of success.

Email is a package before it is prose. It can contain several representations of a message, nested attachments, encoded characters, and earlier correspondence. Turning that package into a string requires decisions about authorship and structure. An extractor that merely removes angle brackets has already made those decisions, whether its designer acknowledges them or not.

We started with a small cabinet of troublesome examples. One message had a useful plain-text body. Another used HTML tables to arrange paragraphs. A third supplied a text alternative that consisted mostly of a promotional footer. There were broken tags, multilingual greetings, and forwarded conversations whose indentation carried meaning. Each example included a short statement of what a reader should be able to recover.

The cabinet changed our evaluation. We no longer asked whether a parser accepted a document. We asked whether neighboring words remained separate, whether invisible presentation code stayed out of the text, and whether the important sentence survived. We also compared the two body alternatives when both existed, rather than automatically trusting the simpler-looking one.

Some choices depended on the eventual task. An index might retain quoted replies because users search for old discussions. A writing analysis might need to distinguish newly written text from earlier messages. A classifier might be distorted by a footer repeated across thousands of otherwise unrelated examples. There was no single cleaning rule that served all three purposes equally well.

The final pipeline retained an extraction status alongside the result. Suspiciously empty output became something to investigate rather than something to celebrate as a short document. Original inputs remained available within the protected working environment so a transformation could be checked later.

The useful lesson was unromantic. Text cleaning deserves fixtures, inspection, and explicit acceptance criteria. A sentence disappearing silently is still a failed computation.
