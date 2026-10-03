---
source_type: ai_synthetic
human_authored: false
author_id: synthetic-lineage-96a517924cae0c074dde
synthetic_lineage_id: synthetic-lineage-96a517924cae0c074dde
synthetic_parent_id: 96a517924cae0c074ddeed34
synthetic_parent_sha256: 7c39ca5ba79dab1951d98221a7adf6d9d1e58dd6933b7eab76912640c1aadcd7
lineage_visibility: tracked
generator_id: agent-7
generation_attempt: 2
---

Four sessions I plan to attend

I am using this year's developer conference to fill gaps in the systems we already operate. These are my choices from the program, and the specific problems I hope each session will help me solve.

Cache boundaries, presented by Morgan Bell, covers where a cache belongs in a request path. Our application caches rendered summaries, but invalidation becomes awkward when several underlying records change. I want a clearer account of expiry, ownership, and what should happen when the cache is unavailable.

Reading a database plan, with Isabel Chen, looks particularly useful. The description promises examples that move beyond adding an index to every slow query. I hope to learn how row estimates, joins, and disk reads interact, and how to tell whether a change improves one query while hurting the broader workload.

Tests that earn their place, led by Ethan Cole, starts with a small Python function and builds a test suite around actual failure modes. That seems like a good session for teammates who have written code for years but still find fixtures and isolation confusing. I am interested in the examples of tests that become brittle after harmless refactoring.

A first month for a new engineer, from Priya Lane, concerns documentation, mentoring, and increasingly independent tasks. We are hiring soon, and our current onboarding plan relies too heavily on whoever happens to be available.

If the schedule changes, I will prioritize the database session. It is the one most likely to affect our incident response immediately. The others should provide practical changes we can introduce gradually.
