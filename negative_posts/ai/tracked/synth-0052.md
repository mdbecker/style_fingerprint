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

The extraction step was where the interesting errors appeared

After selecting articles for our language classifier, I built a small fetcher around the export endpoint. A full crawling framework would have introduced machinery we did not need: the collection already had a fixed list of page revisions and no links to discover.

The client handles thirty revisions per request. It writes raw responses into numbered batches, records completed work in a manifest, and retries temporary failures with a delay. I reduced the batch size after several oversized requests failed halfway through. Resuming from the manifest made that experiment cheap.

Understanding the request was straightforward once I inspected the form submission in the browser. Turning it into a script required another pass: remove cookies, avoid transient headers, and set timeouts deliberately. Copying an entire browser command would have carried unnecessary state into the collection job.

The returned markup was a larger challenge. Tables, references, and templates can swamp the prose, especially on short pages. I used an existing extractor for the first pass, then wrote a record reader for its output. The reader yields one page at a time, preserving the revision reference separately from the text used for training.

I also added an inspection sample for each language. Without that, a parser bug affecting one edition could masquerade as a language-specific signal in the classifier.

The cleaned dataset is now ready for exploration. Next I will compare document lengths, inspect the most frequent character sequences, and establish a simple baseline before making any claims about performance.
