# Agent instructions

## Startup Workflow
1. Read [PROJECT_SPEC.md](PROJECT_SPEC.md) completely on first entry or when it changes. It is authoritative; harness docs do not redefine product scope.
2. Run `./init.sh` to create/update the repository-local `.venv`, then run `.venv/bin/python scripts/harness.py status`; read [session-handoff.md](session-handoff.md) and the latest entry in [progress.md](progress.md). Use `.venv/bin/python scripts/harness.py task <id>` for selected work. [feature_list.json](feature_list.json) is canonical; do not load the entire tracker unless editing or auditing it.
3. Run `git status --short`. Preserve existing user changes. Setup checks only the harness; it does not prove application readiness.
4. Read [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) and [docs/DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md); load architecture and evaluation details only for the selected task.

## Stay in scope
- One feature at a time: at most one `in_progress` leaf task; its parent phase may also be active. Use optional `parent` links for bounded tasks and discovered fixes. Respect inherited phase prerequisites and task dependencies and current user authorization; a roadmap entry is not permission to implement it.
- Distinguish implementation checks from phase quality evaluation. Build runners before downstream consumers require them; never gate an earlier task on a runner created later. Phase gates retain full quality coverage.
- Make minimal, task-scoped changes. Do not add speculative dependencies or choose providers before needed.
- Follow spec §§15–24: establish a fixed evaluation set and measurable dense baseline before optimization. Compare meaningful changes against recorded baseline results.
- Enforce `seller_id` isolation from the first data operation, including baseline ingestion/retrieval; do not defer this invariant to Phase 5.
- Unsupported confident answers are high-severity failures. Grounding, citations, abstention and regression checks are required, not optional polish.

## Verification Commands / Definition of Done
- `./init.sh`: repeatable environment and harness validation, including harness tests and an in-memory Python compile check.
- `.venv/bin/python scripts/harness.py verify all`: full application gates; unavailable checks exit 3; usage errors exit 2; failed checks exit 1.
- `.venv/bin/python scripts/harness.py verify-task phase-0`: run the task's gates and record evidence before promotion to `verified` (substitute a child task ID for task work; phases require all children verified first).
- Follow [repository Definition of Done](docs/DEFINITION_OF_DONE.md). `implemented` is not `verified`; manual inspection or a successful harness check cannot substitute for product tests/evaluations.

## End of Session
- Update task status and blockers in `feature_list.json`; keep incomplete or unavailable verification unverified.
- Append commands, outcomes, evidence paths and next action to `progress.md`.
- Replace `session-handoff.md` with current objective, changed files, blockers and an exact next step. Leave a restartable working tree; report failures rather than concealing them.
