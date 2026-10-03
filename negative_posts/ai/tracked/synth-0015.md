---
source_type: ai_synthetic
human_authored: false
author_id: synthetic-lineage-2bf51a42e0542fc3eb40
synthetic_lineage_id: synthetic-lineage-2bf51a42e0542fc3eb40
synthetic_parent_id: 2bf51a42e0542fc3eb40ca0f
synthetic_parent_sha256: 13cd7328ea9af92296153274e290320b9a2f438c8f3994e4209e9deed1cb000e
lineage_visibility: tracked
generator_id: agent-9
generation_attempt: 2
---

I came back from the analytics conference with a notebook full of package names and only a few ideas I expect to use immediately. Here are the useful bits, organized by the work they might help with.

For a text pipeline that no longer fits in RAM

Keira Bell demonstrated reading records a block at a time, extracting features, and updating an incremental model. The impressive part was the measurement: she displayed memory use through the whole pipeline. A generator at the file boundary did not help when the feature-building step accumulated every document. I want to apply the same measurement to our import job before changing libraries.

For a Python service attached to a larger data platform

The distributed processing session separated three responsibilities: moving messages, running queries, and coordinating jobs. Python was used for the application logic around those systems. The speaker showed retries producing duplicate results, then fixed the output stage so replaying a message was harmless. That demonstration was more memorable than the cluster diagram.

For reporting numbers everyone can agree on

An OLAP talk built a small inventory report with product, location, and date dimensions. The speaker made the definition of available stock explicit before discussing the user interface. Returned goods, reserved goods, and physical goods on the shelf are different measures. Several disagreements I have seen about dashboards are probably disagreements about those definitions.

For preserving tomorrow's analysis

Jonah March argued for storing the event time separately from the ingestion time and retaining the mapping between old and new identifiers. He illustrated both with a subscription service migration. Once the old identifiers disappeared, some apparently simple retention questions became unanswerable. This is a session to watch with the people maintaining your application database.

For evaluating a model beyond one number

The final workshop compared precision and recall at several thresholds, then showed the review workload each threshold would create. The team selecting the operating point needed both views. A model with better recall could still be unusable if it generated more cases than reviewers could inspect.

There was also a useful experiment-runner demo: one configuration described the input columns, split strategy, preprocessing, and estimators. I would use it for baselines, with a careful check that repeated runs do not accidentally reuse the evaluation set for tuning. I missed the closing sessions, and will add them to my watch list when the recordings appear.
