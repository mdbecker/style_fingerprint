---
source_type: ai_synthetic
human_authored: false
author_id: synthetic-lineage-96a517924cae0c074dde
synthetic_lineage_id: synthetic-lineage-96a517924cae0c074dde
synthetic_parent_id: 96a517924cae0c074ddeed34
synthetic_parent_sha256: 7c39ca5ba79dab1951d98221a7adf6d9d1e58dd6933b7eab76912640c1aadcd7
lineage_visibility: tracked
generator_id: agent-8
generation_attempt: 2
---

Sessions I am choosing for the application engineering day

The schedule offers several talks that connect closely to the problems on my desk. Here is my route through it, including the reason for each stop.

Deployment as a sequence of reversible steps — Rowan Mills

Mills will use a small Python web application to demonstrate configuration, rolling replacement, and rollback. I have worked with two configuration systems already, so the interesting part for me is how the operator knows a deployment is safe to continue. The abstract includes health checks and a deliberately broken release.

APIs after the first client ships — Elise Grant

This session examines pagination, versioning, and error responses through the experience of maintaining a public service. I am hoping for concrete tradeoffs around backward compatibility. A clean endpoint diagram is easy to draw; preserving old clients while fixing a poor design is harder.

Interactive experiments with a 3D engine — Mateo Ruiz

Ruiz's laboratory uses game-like tasks to study how people judge motion. The talk covers Python control code, participant input, and reproducible scene settings. It appeals to me because it brings interface design and experimental design into the same discussion. A pleasant task still needs careful measurement.

Cache entries with an expiration date — Harper Lane

The presenter follows a product lookup from database query to cached response. Failure handling, key design, and simultaneous cache misses all appear in the outline. We recently encountered a burst of repeated queries after a restart, so I expect this to be directly useful.

Query plans for ordinary developers — Sora Kim

Rather than listing server settings, Kim will diagnose three slow PostgreSQL queries and explain the evidence behind each change. I want to become faster at deciding whether the problem is query shape, an absent index, or an inaccurate estimate.

A test suite you can understand — Daniel Moss

The closing workshop builds tests around a small booking application. It includes examples of brittle fixtures and overused mocks. I will recommend it to new team members, and I expect to learn something from the discussion of keeping tests readable as requirements change.

These choices leave out several tempting data talks. I will catch those afterward; this track should provide a useful set of practices for the next release.
