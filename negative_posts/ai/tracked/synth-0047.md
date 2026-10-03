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

Six talks on my conference calendar

I am choosing sessions with examples I could explain to a colleague afterward. The following group covers everyday Python, data work, and the less glamorous parts of running a service.

Working with only the standard library — Nia Brooks

Brooks analyzes a directory of unfamiliar log exports without installing extra packages. The outline includes archive reading, iterators, counters, and a simple command interface. I like the constraint. It should reveal how much can be done with tools already present on a restricted machine.

Building a personal article filter — Theo Malik

This session starts with a pile of reading preferences and trains a text classifier to sort a news feed. I am interested in the labels as much as the algorithm: a person's judgment changes, and disagreement is not necessarily a data error. The speaker promises to compare the model with a straightforward keyword rule.

From a city CSV to an honest chart — Lina Hart

The example is a set of public pedestrian counts. Hart will load it in a notebook, identify gaps, align timestamps, and examine weekday patterns. The chart comes after the cleaning decisions. That order makes this a strong choice for anyone beginning with pandas.

What your TLS configuration actually provides — Adrian Snow

Encryption is not something I want to assess from a reassuring browser icon. This talk separates certificate validation, protocol negotiation, and application assumptions. The promised live examples include a connection that succeeds for the wrong reason. I expect to leave with better questions for our security review.

Automating a small fleet — Jules Mercer

Mercer will demonstrate an Ansible playbook on three disposable servers and then rerun it. The second run is the part I want to watch. Changes that appear harmless during a fresh installation can behave differently on machines that already contain configuration.

API design under maintenance — Iris Bell

The final talk follows an endpoint across several client releases. Timeouts, partial failures, and ambiguous error messages are on the agenda. I have marked this one because our oldest client is usually the real constraint when we change the service.

If two sessions conflict, I will favor the one with a hands-on demonstration. The recordings can cover the remainder, but the opportunity to ask about an unexpected result is harder to reproduce later.
