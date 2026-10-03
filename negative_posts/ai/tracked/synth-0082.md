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

A public corpus for routing text by language

The first deliverable for our routing service was not an API. It was a reproducible collection of examples. We wanted a classifier that could direct incoming community posts to the appropriate processing pipeline without using those posts as its initial training material.

I started with public encyclopedia revisions. Language editions supplied labels, while a manifest recorded the exact revisions selected. I combined readership statistics over twelve weeks and sampled from high, medium, and low popularity bands. That avoided allowing a few newsworthy subjects to dominate the training set.

A lightweight downloader handled the manifest in batches. Each response was saved before the batch was marked complete, so a interrupted run could resume. The client used timeouts, limited retries, and a clear identifier. Those details turned out to matter more than the choice of HTTP library.

Cleaning followed collection. I removed navigation fragments, citation blocks, and tables, then kept paragraphs with substantial prose. Pages containing mostly labels or formulas were dropped. I inspected a fixed-size sample from each language to check that the cleanup rules behaved similarly across editions.

The resulting training records contain text and a language label. Revision references live in a companion manifest, where they remain available for debugging without becoming model features.

Next I will examine common character sequences and build a scikit-learn baseline. After evaluation, a message queue will connect the application to prediction workers. Separating those stages makes it easier to tell whether a problem comes from the corpus, the classifier, or the service around it.
