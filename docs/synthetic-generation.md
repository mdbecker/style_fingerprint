# Generating and reviewing synthetic negatives

This is the operational guide for extending the synthetic negative corpus. The [current specification](specification.md) defines requirements; [negative collection policy](negative-corpus.md#blind-synthetic-curation) defines eligibility and the reviewer-only signal catalog. Use this guide for future batches, rather than reproducing a previous run's assignments or counts.

Synthetic examples augment the negative class alongside real other-author writing. The author's real writing remains the positive class. Do not replace real negatives with synthetic examples or fit a model on synthetic examples alone. These are deliberately review-selected negatives, not a representative sample of ordinary AI writing.

## Establish the batch before generating

Record the requested number of new approvals, source scope, storage scope, and completion conditions in ignored `artifacts/ai_negative_generation/`. Distinguish new examples from existing corpus totals. A tracked/untracked quota must be checked separately from the overall count.

Use current eligible positive source files, not cached training views, report excerpts, arbitrary web text, or superseded examples. For an untracked-only request, explicitly restrict sampling to the intended current untracked positive inputs and verify each job's provenance. The sampler's default includes all saved positive source directories; it does not mean untracked-only. Prefer original positives for a new batch. Reviewed synthetic ancestors are supported, but add correlated descendants and require a resolvable ancestry chain.

Allocate unused job sequences and distribute source lineages and generating workers deliberately. The sampler favors less-used lineages, but pending jobs do not count as approvals: parallel assignment still needs a coordinator to prevent over-allocation. Do not reset lineage identity or invent a new source group to evade a cap.

The MVP diversity gates require at least three generators contributing at least twenty approvals each, none contributing more than half the accepted set, at least five original positive lineages, no more than twenty approvals per lineage, and at least twelve signal families. These are algorithm constraints, not a snapshot of the current corpus.

## Keep generation blind and isolated

Use subagents to generate every example. The coordinating agent reviews them independently and must not edit generated prose to insert a tell. Start fresh generator contexts without inherited review discussion. An agent that has seen rejection reasons or the signal catalog is no longer blind for this task.

Give each generator only its neutral source prompts, output destinations, and generation instructions. Do not give it this guide, the signal catalog, reviewer notes, accepted examples, model coefficients, or evaluation results. Restrict reads to assigned prompt files and its own outputs. Avoid asking a worker to inspect another worker's prose before generating an alternative.

The helper prints a neutral prompt and saves a local job:

```sh
.venv/bin/python scripts/curate_ai_negatives.py sample --generator-id writer-a --sequence NEXT_SEQUENCE
.venv/bin/python scripts/curate_ai_negatives.py sample --generator-id writer-b --sequence NEXT_SEQUENCE --positive-root SOURCE_DIRECTORY --parent SOURCE_FILE
```

Replace uppercase placeholders with local values; use a different unused sequence for each new job. `--positive-root` can repeat to restrict eligible sources. Actual private paths and source identities belong only in local ignored records.

The initial prompt asks for an independently authored actual communication on a related situation, preserving medium, audience, communicative purpose, and comparable specificity. It requests a different author/style/tone, similar length within 150–700 usable words, and no quotation or close paraphrase. Supply the helper's prompt rather than improvising instructions about AI style. Use invented replacement names and details while retaining the practical function of the source.

Workers should save each finished output immediately in small batches under ignored artifacts and report progress. A draft is not an accepted corpus entry. Keep workers out of accepted directories. Track the worker that actually produced the chosen output; an alternative written by another worker must not inherit the first worker's identity.

## Review every complete output in two stages

Read the source and the entire generated output together. An opening excerpt, a keyword scan, or a worker's assurance cannot substitute for review. Do not ask the generator to certify its own output.

### Stage one: does it perform the source's communication?

Record concrete evidence for four dimensions:

| Dimension | Review question |
| --- | --- |
| Medium | Is an email still an email, a setup guide still an executable guide, or a technical account still an account of actual work? |
| Audience | Is it addressed to a comparable recipient with appropriate assumed knowledge? |
| Purpose | Does it actually request, dispute, propose, report, or explain what the source was trying to accomplish? |
| Specificity | Does it retain comparable concrete constraints, questions, observations, or steps rather than replace them with generic commentary? |

Topic similarity alone is insufficient. An admissions inquiry must ask the admissions office concrete questions; an essay about how applicants should ask questions fails. Slide feedback must identify changes and analytical questions; commentary about good presentations fails. A project setup guide must provide internally consistent setup and verification steps; an essay praising reproducibility fails. A personal update must communicate with the recipient rather than describe interpersonal communication. Invented replacement facts are acceptable; changing a practical message into a fictional story is not.

Save evidence as local JSON with nonempty string fields `medium`, `audience`, `purpose`, and `specificity`. The helper checks that those fields exist; it does not judge their truth. Evidence must describe this output, not repeat a generic approval template.

For example, an invented feature-request email could have this local record:

```json
{
  "medium": "Email making a feature request",
  "audience": "Maintainers of a shared calendar",
  "purpose": "Ask for an availability filter and offer to test it",
  "specificity": "Describes a failed booking, filter behavior, and a proposed trial"
}
```

This records source fit only; it does not establish a stylistic tell or approve the example.

### Stage two: is there a clear stylistic tell?

Only after source fit passes, use the [reviewer-only catalog](negative-corpus.md#manual-review-catalog) to identify a clear pattern in context. Record its location or construction in local reviewer notes and select the corresponding labels.

An isolated three-item list, an ordinary question, required numbered instructions, or polite professional wording is not enough. Repeated tricolons or parallel constructions can qualify when they form a conspicuous pattern. Formal hedging, nominalization, or an unusually polished register must be sustained and distinguishable from what the source's medium and audience naturally require. A technically appropriate README should not be rejected merely for having headings, nor accepted merely for having headings.

Reject outputs that pass source fit but lack a clear tell. Do not lower the standard to meet a quota or promote all available drafts when generation takes longer than expected. These labels record observable style, not proof of AI authorship.

## Record decisions and retry neutrally

Keep outputs, fit evidence, explanations, attempts, and decisions in ignored artifacts. The helper has no LLM integration or automatic semantic reviewer.

```sh
.venv/bin/python scripts/curate_ai_negatives.py review --job JOB_ID --input LOCAL_OUTPUT --reject
.venv/bin/python scripts/curate_ai_negatives.py review --job JOB_ID --input LOCAL_OUTPUT --approve --signals REVIEWER_LABELS --source-fit LOCAL_FIT_JSON
```

Use catalog IDs separated by commas for `REVIEWER_LABELS`; never include them in generator prompts. The rejection command returns the neutral retry prompt. Ask for a new version as a different author with a substantially different style/tone, preserving medium, audience, purpose, and specificity. Do not disclose the rejection reason or ask for a particular tell. A different register can be requested without naming the reviewer criterion, but do not make every retry formal or steer the whole batch toward one recognizable template.

Reuse the job for retries. Archive the prior draft locally before requesting another version at the same output path. After five consecutive rejections, rotate to a different blind worker. Register that worker before recording its next decision using `review --generator-id DIFFERENT_WRITER`. The helper resets the rejection streak on rotation; do not reset counters manually or bypass the cap. Every replacement still receives both review stages.

Approval additionally checks 150–700 usable words, stable parent hashes and provenance, the lineage cap, no copied twelve-word sequence, and no exact long source sentence of at least eight usable words. A failed hygiene check is not approval. Accepted files are created exclusively by the helper; reviewers must not patch prose or front matter to force admission. Reviewer labels and fit notes remain outside accepted text and model predictors.

## Preserve visibility and audit existing mistakes

Complete tracked ancestry permits `negative_posts/ai/tracked/`. Any private, ignored, outside-repository, or untracked ancestor permanently forces `negative_posts/ai/untracked/`. Copying a private-source rewrite into a public folder does not make its ancestry public. Unknown synthetic ancestry is refused. Never manually override placement, publish private source identifiers or excerpts, or add local review databases to public attribution inventories.

If review discovers a systematic problem in an admitted batch, audit every affected tracked and untracked example against its source. Record retain/replace decisions locally. Preserve the old prose and decisions in an ignored archive, explicitly supersede rejected approval records, and remove those files from active corpus discovery. Check descendants before moving a parent: provenance must remain resolvable or affected descendants must also be replaced. Keep a recoverable audit trail; do not silently overwrite accepted text or erase the original decisions. The helper has no automatic supersession command.

Regenerate replacements through blind subagents and review them again. Admit good examples as they pass rather than leave an empty destination until the whole batch finishes. Report accepted counts separately from drafted or assigned counts.

## Close the batch before retraining

```sh
.venv/bin/python scripts/curate_ai_negatives.py status
.venv/bin/python scripts/check_docs.py
.venv/bin/python -m pytest tests/test_ai_negative_curation.py tests/test_negative_policy.py tests/test_documentation_policy.py
```

`status.complete` represents the initial MVP gate of at least one hundred approvals plus diversity and integrity checks. It does not certify a larger requested batch or an untracked quota. Explicitly verify the requested total and storage split, active approvals versus files, required fit evidence, correct generating identities, parent hashes, ancestry, caps, and accepted-file hashes. Confirm private outputs are Git-ignored and absent from Git-included files. Audit publishable files for private text and identities; a literal scan cannot certify every paraphrase.

Only after generation and review are complete, rerun evaluation with model selection and then refit production using its frozen choices:

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false .venv/bin/python -m style_fingerprint evaluate --device cpu --offline
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false .venv/bin/python -m style_fingerprint build --device cpu --offline
```

These commands use the saved configuration and local pinned encoder. Check that saved source directories still represent the intended real positive and negative inputs. A changed negative corpus invalidates prior supervised artifacts; unchanged-text embedding caches may be reused. Evaluation performs model selection; production build consumes the frozen configuration. Wait for each command to finish successfully. Preserve the previous evaluation locally for inspection, but do not claim a fixed-test improvement when the corpus or grouped splits changed.

Full model selection can take substantially longer than production refitting. Redirect logs to ignored verification artifacts when useful, monitor completion and process activity, and remember that buffered output may remain empty while computation continues. Do not restart an active run merely because it has not printed progress.

Verify production corpus counts and negative hashes against the frozen configuration, load the saved model, and run an invented-prose scoring check. The regenerated report is `artifacts/report.html`. Examine real email negatives, real technical-blog negatives, synthetic negatives, and real-positive recognition separately. Strong synthetic rejection can coexist with poor discrimination between real writers. Save metrics, split inventories, checks, and reports under ignored artifacts, never as dated maintained documents.

If the user requests the app, start it only after the production rebuild. An already-running server retains its loaded model, so arrange a restart before claiming it uses new artifacts.

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false .venv/bin/python -m style_fingerprint serve --device auto --host 127.0.0.1 --port 8000
```

Verify `/api/health` and a scoring request, and provide the localhost URL. Stop the server when asked. Generating data, retraining, serving, and publishing are separate actions; do not publish private artifacts as part of this workflow.
