# Development workflow

## Start and resume
Read AGENTS.md → authoritative spec → run `./init.sh` to create/update `.venv` from `requirements.txt` → `.venv/bin/python scripts/harness.py status` → session-handoff.md → latest progress.md entry. Use `.venv/bin/python scripts/harness.py task <id>` for the selected task; the full JSON tracker is needed only when editing or auditing state. Inspect `git status --short`. Python 3.10+ is supported and enforced by bootstrap; Phase 2 has no third-party application dependencies, credentials or services. The accepted but unimplemented Phase 3 baseline requires a local Ollama service and `qwen2.5:1.5b-instruct`; see `docs/decisions/0003-phase-3-local-generation.md`. A failing startup must be investigated before unrelated work.

Select one authorized leaf task whose own dependencies and parent phase entry dependencies are `verified`. Open its phase as `in_progress`, set the task `in_progress`, and update the handoff with its ID and bounded objective. Load only its spec sections, architecture and evaluation contract next. Application work starts at Phase 1 (`p1-policies`); later phases still need an explicit implementation request.

## State contract
`feature_list.json` is the canonical machine-readable tracker. Keep IDs stable and acceptance criteria traceable to the spec. States:
- `not_started`: no implementation.
- `in_progress`: one active task with verified dependencies.
- `implemented`: deliverables exist, but verification is pending or unavailable.
- `verified`: required checks produced successful external evidence, for the recorded snapshot.
- `blocked`: set a concrete `blocker` and next action; this is not completion.

Move not_started → in_progress → implemented → verified. Block unfinished work at any point; resume through in_progress or implemented as appropriate. Reopen verified tasks when relevant inputs, requirements or implementation change; clear their evidence links and mark dependent results needing revalidation. Status edits are ordinary reviewed JSON changes, except promotion: use `verify-task` only. Never copy old reports to certify changed work.

## Phases and bounded tasks
The existing `features` array and `schema_version: 1` remain. `parent` is optional: omit it for top-level phases or legacy standalone tasks. Child tasks keep all existing fields and add, for example, `"id": "p2-ingestion", "parent": "phase-2"`. Parent links must refer to a top-level phase; nesting is intentionally one level.

- A phase groups scope and retains its acceptance criteria and full verification gates. Child tasks narrow deliverables and gates; they do not replace phase acceptance.
- Children inherit the parent's **entry dependencies**, not the parent itself. List sibling prerequisites in `dependencies`. Never depend on your own parent or create a completion cycle through a later phase.
- Only one **leaf task** may be `in_progress`; its phase may also be `in_progress`. Set the phase in progress before starting a child. Phase status is explicit, not automatically computed.
- Verify each implemented child with `verify-task <child-id>`. Once all children are verified, set the phase to `implemented` and run `verify-task <phase-id>` for its full gates. Children passing alone never auto-verify a phase.
- Add newly discovered fixes as child entries with stable IDs, bounded acceptance criteria, appropriate gates and dependencies. Keep them within authorized spec scope. Reopen a verified parent and clear its evidence before adding unfinished work; reopen affected dependents as required. Do not delete unfinished children to pass a phase.
- The seeded tasks are a starting decomposition, not an exhaustive or immutable backlog. Split further when a task cannot be reviewed and verified independently. Preserve coverage of phase acceptance criteria and do not invent application progress.

## Gate staging and progressive disclosure
Feature implementation checks cover the behavior that exists at that point. Complete quality evaluation belongs to the evaluation task and the phase closure. A task may implement its own real checks; it must not need a runner or feature built by a downstream task to unlock that downstream task.

- Phase 1: p1-policies and p1-annotations use harness only to advance the preparation workflow. This certifies control-plane consistency, **not corpus/annotation quality**. p1-dataset-checks implements/wires the dataset validator and validates the whole corpus and annotations; Phase 1 cannot close until dataset passes.
- Phase 2: p2-ingestion creates unit/integration/isolation checks alongside ingestion, covering only implemented behavior. Extend coverage as chunking/indexing/retrieval land. p2-retrieval-evaluation builds the complete retrieval evaluator; earlier tasks do not require it.
- Phase 3: generation and citations require harness/unit/integration/isolation; p3-generation-evaluation builds generation/regression/system runners and runs complete phase quality checks.
- Phase 4: evidence detection/fallback use implementation checks (and already available generation checks where applicable); p4-abstention-evaluation builds the full abstention evaluator. The phase retains its full quality gates.
- Later phases reuse established runners and extend cases as necessary. A fixed corpus, source updates or gate changes must not weaken acceptance criteria. Unavailable required checks remain unavailable, never skipped into success.

`status` is a compact read-only view of the active or next pending milestone, active task, eligible leaves, tasks awaiting verification and dependency/explicit blockers. An unopened phase can expose an eligible first child with an instruction to open the phase first. Eligibility describes starting prerequisites, not gate availability or authorization. All-verified children still require phase verification. `task <id>` returns only that record plus effective (including inherited) dependencies and existing evidence paths; it does not load report bodies. Both validate state, return 1 for invalid state, and create no evidence. Unknown task IDs return 2.

## Commands
```sh
./init.sh
.venv/bin/python scripts/harness.py status
.venv/bin/python scripts/harness.py task p1-policies
.venv/bin/python scripts/harness.py check
.venv/bin/python scripts/harness.py verify harness
.venv/bin/python scripts/harness.py verify unit
.venv/bin/python scripts/harness.py verify integration
.venv/bin/python scripts/harness.py verify dataset
.venv/bin/python scripts/harness.py verify retrieval
.venv/bin/python scripts/harness.py verify generation
.venv/bin/python scripts/harness.py verify abstention
.venv/bin/python scripts/harness.py verify isolation
.venv/bin/python scripts/harness.py verify regression
.venv/bin/python scripts/harness.py verify system
.venv/bin/python scripts/harness.py verify all
.venv/bin/python scripts/harness.py verify-task phase-0
```

Exit 0 = checks actually passed; 1 = failed checks/invalid state; 2 = CLI usage error (including unknown commands, gates or task IDs); 3 = unavailable checks or bootstrap prerequisites. Dataset, unit, integration, retrieval, and isolation gates are implemented; generation, abstention, regression, and system remain unavailable. Aggregation preserves failure first, then usage error, then unavailable; it returns 0 only if every gate passed. `all` runs harness, unit, integration, dataset, retrieval, generation, abstention, isolation, regression, system and preserves failure. `verify-task` requires implemented/verified state and verified dependencies, runs every required gate, and promotes only after all pass. A failed/unavailable/timed-out recheck downgrades the target to implemented and clears its successful evidence links. Cascade invalidation moves affected in_progress/implemented/verified dependents (including inherited phase prerequisites) to blocked with a revalidation reason and clears their active evidence references. Verified parents with unfinished children reopen as implemented, or become blocked if their own prerequisites are no longer verified. This repeats until dependency and parent invariants hold. Historical evidence files are never removed. Candidate state is validated before replacement; an invalid candidate returns 1 without saving the tracker. `verify-task` preserves exit 3 when checks are unavailable, rather than flattening it into failure.

Resume cascaded work explicitly after prerequisites are verified: clear its blocker, move the phase/task to in_progress or implemented as appropriate, then run verify-task for fresh evidence. Upstream recovery does not automatically restore downstream verification. This uses the existing reviewed JSON workflow; no new state-transition CLI is introduced.

Every gate has a timeout in seconds in `GATE_TIMEOUTS` in scripts/harness.py: harness/dataset 120, unit 60, integration/isolation 300, retrieval 600, generation/abstention/regression/system 900. These are runner budgets, not product latency targets. Adjust the corresponding entry when real runners have measured needs. `subprocess.run` terminates and waits for the direct gate process on timeout; future runners that spawn subprocesses must manage their own children. A timeout returns failure 1, records `timed_out: true`, `timeout_seconds`, available partial stdout/stderr and a timeout diagnostic, and cannot promote a task. Other gates in a batch still run. Unimplemented gates continue returning unavailable 3.

Command records in `verification/evidence/` include UTC time, command, exit status, stdout/stderr and a SHA-256 input snapshot. Snapshot excludes mutable session/status/evidence files and caches; task definitions are included separately. Reports are historical evidence, not a guarantee about later edits. Keep referenced reports under version control. The harness is not tamper-proof against an agent editing its own checks: review changes to gates and never treat self-authored summaries as test results.

## Adding real verification later
Replace the explicit unavailable gate in `scripts/harness.py` only when a real runner and fixtures exist. Capture its actual exit code and machine-readable results. Zero collected cases, all-skipped tests, missing credentials/data/services, invalid output and absent baseline must fail or return unavailable. Do not use echo, syntax-only checks or unconditional success as product gates. Retain negative tests for those conditions. Implement gate integrations alongside the corresponding milestone, without removing required gates to get a green result.

## End of session
Save reports first, then update task evidence/state; append progress (date, task, changes, commands/results, blockers, next step), then replace the short handoff. Record partial progress honestly. Do not silently discard existing user edits or commit secrets/customer data. No background hooks or agents are required.

## Decisions and experiments
Use `docs/decisions/NNNN-title.md` for consequential choices: status, context/spec links, decision, alternatives, consequences and evidence. No mandatory ADR for routine edits. Use [evaluation contract](EVALUATION.md) for experiments; a few example queries do not establish improvement.
