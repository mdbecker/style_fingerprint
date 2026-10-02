# Repository instructions

The authoritative product requirements are [docs/specification.md](docs/specification.md). Historical supplied specifications are reference material only; subsequent user instructions take precedence. Keep the small local MVP architecture.

## Tests-first development

Use BDD red → green → refactor. Before each functionality stage, write behavioral tests, run them, confirm the expected failures, then implement and make the relevant suite green. Mock only the external encoder boundary in the default suite. Keep real inference in marked integration tests. **Tests-first development is required; publishing every development artifact is not.**

## Maintained documentation

Maintain existing documentation in place. Do not create per-task, per-stage, dated, red/green transcript, or intermediate evaluation files under `docs/`. BDD requires tests before implementation, not committed test logs. Store generated evidence in ignored `artifacts/`. Before adding a document, check whether an existing document covers its purpose. Remove or consolidate superseded information when updating behavior.

The explicit maintained file list is enforced by `scripts/check_docs.py`: documentation index, current specification, consolidated historical specifications, implementation, one development note, corpus handling, evaluation, negative collection/licensing, negative attribution inventory, and curated negative source inputs. Change that list only for a justified new maintained purpose, not a task-specific report.

Generated test transcripts, intermediate/final metrics, environment captures, split inventories, privacy scan results, and HTML model reports belong under `artifacts/`. Commit a generated report only when the user explicitly requests publication; add a deliberate inventory exception if needed. Otherwise link to local ignored output from the user-facing response, not maintained docs. Keep verification in the single concise `docs/development.md` note; update it in place rather than appending a task diary.

## Privacy and attribution

Never publish private corpus text, filenames, or document IDs. Both `work_corpus/` and `gmail_corpus/` are private ignored inputs. Saved artifacts, candidate explanations, retrieval excerpts, and exact split metadata can also contain private information. Use invented test prose and generic source names. Audit all Git-included files when changing corpus handling or documentation. Preserve public source attribution, pinned provenance, and license terms; do not strip licenses during cleanup.

## Verification

Run `.venv/bin/python scripts/check_docs.py` and the relevant pytest tests before finishing. The default pytest suite includes documentation policy checks. Validate links and inventory when consolidating docs. Write any desired command output to `artifacts/verification/`, never `docs/`. Avoid repeating expensive real training unless behavior changes require it.
