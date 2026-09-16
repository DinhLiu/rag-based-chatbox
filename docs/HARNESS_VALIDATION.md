# Initial harness validation

Date: 2026-09-16. Scope: development control plane only.

## Spec alignment review
- PROJECT_SPEC.md was read completely before editing and remains unchanged.
- Phase 0–9 tasks map to §28, with acceptance criteria and spec section references. Dependencies permit core deployment without requiring optional retrieval optimization or policy-gap analytics. No application implementation is included.
- Architecture follows §§6–15, 27; technologies remain undecided. §16 exclusions and §30 extensions remain outside the initial baseline.
- docs/EVALUATION.md carries §§17–24 requirements: fixed 30–50-case dataset, Recall@5/MRR@10, generation faithfulness/relevance/completeness/citations, abstention precision/recall/False Answer Rate, system metrics and baseline comparisons.
- Tenant isolation applies from first ingestion/retrieval (§§6, 13), with lifecycle regression coverage (§11). Unsupported confident answers block acceptance as high-severity failures (§20).
- Definition of Done and task promotion require executable evidence (§§25–26); no numeric targets or evaluation scores have been invented.

## Start/resume walkthrough
A fresh agent can follow README → AGENTS → spec/state/handoff → ./init.sh → scoped docs. Startup uses only Python standard library and shell, installs nothing and does not need the author's skill directory. Only the optional external skill audit requires that directory and Node.

Session persistence uses reviewed repository files: task status/dependencies/evidence in JSON, appended progress, and a short replaceable handoff. The next authorized application step is Phase 1; the current request stops at the harness.

## Verification and limits
The behavioral suite exercises invalid task state, absent/failed/unavailable evidence, dependencies, active-task limits, explicit unavailable application gates, empty/all-skipped tests, snapshot changes, promotion and failed rechecks. Tests use synthetic records only in temporary directories, never as real product evidence.

External skill validation and benchmark reports live in verification/evidence/skill-validation.json and skill-benchmark.json. Their structural scores and bundled skill eval-coverage scores are not application quality measurements and do not establish real multi-session agent effectiveness. Run representative development sessions before making that claim.

Actual harness runs and task evidence are recorded alongside those reports. All application test/evaluation gates remain explicit unavailable placeholders. No RAG baseline or application evaluation has run.

## Follow-up: exit codes and task granularity

CLI usage errors now return 2 and unavailable checks return 3, including aggregate/task verification and bootstrap. Historical reports with unavailable exit 2 retain their original meaning; new reports use the split contract. Optional parent links preserve schema version 1 and existing phase IDs while adding bounded child tasks. Validation covers parent references, inherited prerequisites, one active leaf, completion cycles, unfinished child rejection and parent evidence requirements. Phase 0 is reopened and reverified for these changes.

## Follow-up: gate availability and focused state views

Phase 1 preparation and Phase 3 implementation no longer require downstream quality evaluators. The same staging issue was corrected for Phase 2 retrieval and Phase 4 abstention. Runner ownership is explicit in task acceptance criteria; full phase gates remain intact. A scheduling regression test simulates capability creation in dependency order (not product results). Status/task view tests cover eligibility, explicit/dependency blockers, phase closure, invalid IDs/state and read-only behavior. Application evaluators remain unavailable.
