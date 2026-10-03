---
source_type: ai_synthetic
human_authored: false
author_id: synthetic-lineage-96a517924cae0c074dde
synthetic_lineage_id: synthetic-lineage-96a517924cae0c074dde
synthetic_parent_id: 96a517924cae0c074ddeed34
synthetic_parent_sha256: 7c39ca5ba79dab1951d98221a7adf6d9d1e58dd6933b7eab76912640c1aadcd7
lineage_visibility: tracked
generator_id: agent-9
generation_attempt: 2
---

The automation workshop promises to update a small group of application servers without taking the whole service offline. I am interested in the point where the neat deployment diagram meets a machine that refuses to cooperate. The speaker has included a failed update in the demonstration, which makes the session especially appealing.

A few more picks from the conference schedule:

APIs with customers attached — Eva Marsh

This talk covers the evolution of an API used by several independently maintained clients. The abstract names pagination, optional fields, and error responses as the difficult parts. I like that focus. It is possible to produce a very elegant endpoint that still makes every client author miserable when something goes wrong.

A game as an experimental instrument — Theo Birch

Theo's team uses a Python 3D environment to study how people anticipate moving objects. The software records choices under controlled conditions rather than simply collecting game scores. I want to see how rendering, input, and experiment timing are kept distinct. That separation should be useful to anyone building interactive measurement tools.

An in-memory cache under real load — Lina Hart

The session explains expiration, eviction, and the rush of requests after a popular key disappears. Our own cache has mainly been discussed as a way to reduce database traffic. I expect the talk to raise better questions about stale values and behavior when the cache is unavailable.

Reading PostgreSQL's explanation — Omar West

This workshop diagnoses a slow query with an execution plan. The presenter will compare the planner's estimates with the rows actually processed and show how joins create large intermediate results. I would prefer to understand those steps before buying a larger machine or adding another speculative index.

Testing a small application — Cora Reed

The last selection starts with an ordinary Python parser and adds behavioral tests. The examples include missing fields and malformed values, which should help explain how a useful failure differs from a crash. I have suggested it to a teammate who is learning automated testing and would benefit from seeing the entire loop in one sitting.

These talks fit the work waiting for me after the conference. I may add a more exploratory session if the timetable allows, but this is already enough material to keep me busy on the train home.
