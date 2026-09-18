# Session Progress Log

## Current State — Last Updated: 2026-09-16

Current Objective: p1-annotations verified. Phase 0 remains verified. phase-1 is in_progress; p1-dataset-checks is not started. Dataset validator, RAG baseline, and application runners remain unimplemented.

### What changed
- Read PROJECT_SPEC.md completely before editing and retained it unchanged.
- Filled the existing empty AGENTS.md and updated README.md.
- Created architecture, development workflow, Definition of Done, evaluation contract, initial decision and harness-validation notes.
- Added Phase 0–9 task state, repeatable bootstrap, evidence runner and behavioral control-plane tests.
- Preserved the existing .gitignore and LICENSE; no application dependencies or technology choices introduced.

### Verification Evidence
- `python3 scripts/harness.py verify-task phase-0` — exit 0; 16 harness tests, state checks and static compilation passed. Evidence: `verification/evidence/876978c1d31c4448a76cd220939e76fa-harness.json`.
- `node /home/liu/.agents/skills/harness-creator/scripts/validate-harness.mjs --target . --json` — exit 0; all five subsystems 5/5, overall 100/100. Report: `verification/evidence/skill-validation.json`.
- `node /home/liu/.agents/skills/harness-creator/scripts/run-benchmark.mjs --target . --output verification/evidence/skill-benchmark.json` — exit 0; scaffold self-check passed. Structural benchmark only; bundled skill eval coverage is not RAG evaluation coverage.
- `python3 scripts/harness.py verify all` — exit 2 as expected; all nine application gates unavailable, with separate JSON records. No application checks counted as passed.
- Clean-copy startup from outside the repository — exit 0; premature Phase 1 verification rejected with exit 1. Report: `verification/evidence/clean-start.json`.
- `python3 scripts/harness.py check` and `git diff --check` — exit 0.
- Spec/startup/completion review: `docs/HARNESS_VALIDATION.md`.

### Issues found and fixed
- Skill structural audit initially missed the wording of the static compilation check; made the command description explicit and reran the audit.
- Empty or wholly skipped harness test suites now fail explicitly; regression tests cover both.

### Blockers
No blocker for p1-annotations. Dataset, retrieval, generation and other application gates remain unimplemented. Annotation quality is not certified by the harness gate.

### Next Session
Read session-handoff.md. Stop after p1-annotations. When authorized, start p1-dataset-checks.

## Follow-up — 2026-09-16: bounded tasks and exit codes

- Preserved schema_version 1, phase IDs, phase acceptance criteria and product scope; added optional parent links and bounded child tasks across the roadmap. Phase 0 child tasks track this follow-up.
- Exit contract: 0 passed, 1 failed/invalid state, 2 usage error, 3 unavailable. Historical unavailable=2 records above predate this change; new runs use 3.
- Child tasks inherit phase entry prerequisites. Only one leaf may be active; a phase can be active alongside it. Parent verification requires every child verified plus phase gate evidence. Cycles and invalid parent links fail validation; failed child rechecks reopen verified parents.
- Added docs for newly discovered tasks, explicit phase state and reopening affected work. No application features or dependencies added.
- Fixed repeated dependency traversal during validation by visiting each graph node once.
- Validation: 27 behavioral tests pass, including real CLI exit-code separation, hierarchy rules and parent reopening. ./init.sh passes; full verify all returns 3, invalid gate returns 2, as recorded in verification/evidence/exit-code-contract.json.
- Skill validator: 100/100; instructions, state, verification, scope and lifecycle each 5/5. Report: verification/evidence/skill-validation-task-hierarchy.json.
- Verified p0-exit-codes, p0-child-tasks and phase-0 with verify-task; feature_list.json links their fresh command evidence.
- Next: stop after harness work. When authorized, open phase-1 and select p1-policies; add or refine bounded child tasks as discoveries require.

## Follow-up — 2026-09-16: staged quality gates and focused views

- Corrected Phase 1: policies/annotations require harness only; dataset-checks implements/wires the dataset validator and validates the complete phase. Preparation task verification does not claim corpus quality.
- Corrected Phase 3: generation/citations require harness, unit, integration, isolation. generation-evaluation owns complete generation, regression and system runners/gates.
- Audited other phases: deferred retrieval gate to p2-retrieval-evaluation and abstention gate to p4-abstention-evaluation; p2-ingestion explicitly creates implementation checks alongside its behavior. Full phase acceptance gates are unchanged.
- Added read-only status and task <id> views. Agent startup now uses focused views rather than loading the full tracker. Eligibility describes start prerequisites, not available verification or authorization.
- Added p0-gate-order-and-views and verified it, then reverified phase-0. Evidence: verification/evidence/db5666f67802413ab180088134fff770-harness.json and verification/evidence/4dd21690f85a478fac5f648c21684798-harness.json.
- Validation: 40 tests passed, including simulated gate-capability scheduling, explicit/dependency blockers, phase closure, CLI errors and no state/evidence writes from views. This scheduling simulation is not application evaluation.
- Skill validator: 100/100; each of five subsystems 5/5. Report: verification/evidence/skill-validation-gate-staging.json.
- Actual status/task commands returned 0; unknown task returned 2; verify all returned 3. Report: verification/evidence/gate-staging-and-views.json. No application gate passed.
- Current milestone view selects phase-1; p1-policies is eligible once that phase is opened. Phase 1 remains not_started and still requires a new implementation request.

## Audit — 2026-09-16: harness reliability assessment

- Scope: review only; no application work or harness implementation changes. Existing task states/evidence links remain unchanged; verified entries are historical certifications.
- Read full spec, startup/state docs, harness implementation, both behavioral suites and evaluation contract.
- `./init.sh`: exit 0; 40 tests passed. Evidence: verification/evidence/7d750a641f604f86bf6aaddfdaefc62c-harness.json.
- Skill structural validator: all five subsystems 5/5, 100/100. This does not establish recovery correctness or product readiness.
- `python3 scripts/harness.py verify all`: exit 3; harness passed (verification/evidence/33c173a962d9430d9da43ff06afe570a-harness.json); nine application gates unavailable.
- Confirmed P2 recovery defect in temporary repository copy: open phase-1 (check exits 0), inject a failing harness test, reverify phase-0 (exit 1, downgraded to implemented), remove failing test; both status and verify-task phase-0 still exit 1 with phase-1: unverified dependency. Failed rechecks reopen only the target/parent, not dependent tasks, leaving a state rejected by the global precheck. Original tracker and tests were not altered.
- Next: when repair is authorized, make failed-recheck transitions preserve valid dependent state and add a real CLI regression for failure → repair → reverify. Also expose historical/stale evidence explicitly and test representative multi-session work before claiming operational effectiveness. No Phase 1 implementation authorized by this audit.

## Repair — 2026-09-16: p0-reverification-timeouts

- Authorized priorities 1–3 completed using Python standard library. Reviewed docs/decisions/0001-harness-only.md; preserved its dependency-free and unavailable-gate decisions. New semantics are recorded in docs/decisions/0002-reverification-recovery.md.
- Failed/unavailable/timed-out rechecks now cascade over direct/inherited prerequisites and parent completion until state is valid. Affected dependents become blocked (implemented would violate prerequisite invariants); verified parents reopen. Clear active evidence references only; retain report files. Recovery explicitly resumes/reverifies dependents.
- verify-task validates candidate state before saving. Every gate now has a finite timeout; failures record budget, timeout flag, partial output and diagnostic. Direct gate processes are killed/waited on by subprocess.run; descendant cleanup belongs to future runners.
- Changed scripts/harness.py, added tests/harness/test_recovery_and_timeouts.py, updated docs/DEVELOPMENT.md and task tracker. Priorities 4–10 deferred as described in ADR 0002; no product work started.
- ./init.sh passed during implementation. Final verification: 47 tests passed including actual CLI failure/recovery, unavailable cascade, parent/inherited dependencies, historical evidence retention, invalid candidate refusal, and actual subprocess timeout with promotion rejection.
- python3 scripts/harness.py verify-task p0-reverification-timeouts: exit 0; verification/evidence/a4ed6f86f98b4b1eb7920edb2dff817b-harness.json.
- python3 scripts/harness.py verify-task phase-0: exit 0; verification/evidence/aa70101f26554bcf898f0c6f5a7b6af6-harness.json.
- python3 scripts/harness.py verify all: exit 3, harness passed (verification/evidence/92377d5806dc4258bb9f58ffedad3ee1-harness.json); all nine application gates unavailable as expected. No product evaluation success claimed.
- Next: stop after authorized priority repairs. When application work is authorized, inspect p1-policies; consider scoped snapshots/evidence and transitions during Phase 1–2. No blocker for this repair.

## Follow-up — 2026-09-16: p1-policies

- Authorized Phase 1 application work for p1-policies only. Opened phase-1 as in_progress, then implemented and verified the initial policy corpus.
- Added `eval-policy-corpus` version 1 under `data/raw/`: catalog `corpus.json` plus 9 Aurora and 3 Beacon markdown policies. Identities are `(seller_id, document_id, version)`; `document_id` repeats across sellers; `seller_id` is required on later reads. Intentional gaps (late returns, discounted items, water damage, international shipping, late-delivery compensation) and Beacon's conflicting numbers are left for later annotation/isolation work.
- Did not create evaluation questions, `evals/datasets/`, or a dataset runner. Did not start p1-annotations or p1-dataset-checks. Harness-only verification does not certify corpus or annotation quality.
- Updated EVALUATION.md, ARCHITECTURE.md, README.md, DEVELOPMENT.md authorization wording, and feature_list.json dependency_note.
- Startup: first `./init.sh` in the sandbox failed when timeout tests could not SIGKILL child processes (PermissionError). Rerun outside the sandbox: `./init.sh` exit 0; evidence `verification/evidence/075e7cbaa4534f79b1724cc1f8855ce4-harness.json`.
- `python3 scripts/harness.py verify-task p1-policies`: exit 0; 47 harness tests passed; evidence `verification/evidence/3a25d8308ab1447b9003e94034379eab-harness.json`. Task status verified. Dataset and other application gates were not run and remain unimplemented.
- Next eligible task: p1-annotations. Phase 1 stays in_progress until remaining children and the dataset gate are done. A roadmap entry is not authorization to start p1-annotations.

## Follow-up — 2026-09-16: p1-annotations

- Authorized p1-annotations only. Kept phase-1 in_progress. Did not start p1-dataset-checks or any RAG pipeline.
- Added `eval-policy-questions` version 1 at `evals/datasets/eval-policy-questions-v1.json`: 40 cases against `eval-policy-corpus` v1. Distribution is 16 simple, 8 paraphrased, 6 multi-policy, 6 unanswerable, 4 ambiguous/adversarial. Each case has `case_id`, `seller_id`, `query`, `answerable`, `expected_sources`, and `expected_source_identity` (`seller_id`, `document_id`, `version`, section). Answerable cases include `expected_answer_points`. Four Beacon cases cover overlapping `document_id` values with conflicting rules.
- Did not implement a dataset validator or wire the dataset gate. Harness-only verification does not certify annotation quality.
- Updated EVALUATION.md, ARCHITECTURE.md, README.md, and feature_list.json.
- Startup: first `./init.sh` in the sandbox failed when timeout tests could not SIGKILL child processes (PermissionError). Evidence: `verification/evidence/9fac34c436684d7db440a1d217f4aa21-harness.json`. Rerun outside the sandbox: `./init.sh` exit 0; evidence `verification/evidence/344436e9931e4667ba91c56c32ad0c6a-harness.json`.
- `python3 scripts/harness.py verify-task p1-annotations`: exit 0; 47 harness tests passed; evidence `verification/evidence/209bb01e170b4ad78ebf33d52eaca563-harness.json`. Task status verified.
- `python3 scripts/harness.py verify dataset`: exit 3; unavailable. Evidence `verification/evidence/b03d16e2c62647a6910205adec8916d1-dataset.json`. Not treated as passed.
- Next eligible task: p1-dataset-checks. Phase 1 stays in_progress until that child and the dataset gate are done. A roadmap entry is not authorization to start p1-dataset-checks.

## Follow-up — 2026-09-16: p1-dataset-checks

- Authorized and completed only `p1-dataset-checks`; no ingestion, retrieval, generation, or other downstream task was started.
- Added the dependency-free `scripts/validate_dataset.py` validator and wired the harness `dataset` gate. It checks fixed corpus/dataset version binding, unique seller-scoped document identities and paths, document headers and sections, 30–50 case count, exact 40/20/15/15/10 distribution, case shape, seller/source identity consistency, and meaningful-token support for answer points in cited sections. Empty and skipped datasets fail.
- Added six mutation tests under `tests/dataset/` for the real fixtures, empty cases, wholly skipped cases, cross-seller/missing-section identities, unsupported answer points, and version/distribution mismatches. Updated the harness availability test and Phase 1 documentation.
- Startup `./init.sh` passed. Pre-promotion dataset checks passed, including `verification/evidence/ea41383a4853477589e5c27d28d70ae6-dataset.json`; `git diff --check` and `python3 scripts/harness.py check` passed.
- `python3 scripts/harness.py verify-task p1-dataset-checks` exited 0 and promoted the task to verified. Harness evidence: `verification/evidence/018ea1603f8f4af394c8604a79892bed-harness.json` (48 tests). Dataset evidence: `verification/evidence/1a2982451f5f4268a027348d271af5e8-dataset.json` (6 mutation tests; 40 collected/executed, 0 skipped, 0 failed checks; 12 documents, 2 sellers; distribution 16/8/6/6/4).
- No blockers. All Phase 1 children are verified; the next eligible action is Phase 1 closure: set `phase-1` to implemented and run `python3 scripts/harness.py verify-task phase-1`. Phase 2 remains unauthorized and must not start before Phase 1 is verified.

## Follow-up — 2026-09-16: phase-1 closure and p2-ingestion

- Authorized `p2-ingestion`. Closed `phase-1` first because it is an inherited prerequisite: set implemented, then `python3 scripts/harness.py verify-task phase-1` exited 0. Evidence: `verification/evidence/c70dd85b63a543e6808358b55762ed41-harness.json` (48 tests) and `verification/evidence/75549ed3bb3045dc93a605c9b6e97726-dataset.json`. Opened `phase-2` and completed only `p2-ingestion`. Did not start `p2-chunking`, indexing, or retrieval.
- Added stdlib `src/ingestion.py`: seller-scoped parse/clean for PDF, Markdown, TXT, and direct text, preserving available source, section, page, seller, and version metadata. PDF extraction covers Latin text operators and FlateDecode only. Corpus reads are filtered by `seller_id`; cross-seller paths are rejected.
- Wired real `unit`, `integration`, and `isolation` gates. Added 4 unit, 3 integration, and 3 isolation checks that do not chunk, index, or retrieve. Updated harness availability tests and the recovery fixture so an explicit unavailable unit runner is still tested now that the real unit suite exists.
- Sandbox `./init.sh` failed on SIGKILL in timeout tests (`verification/evidence/98d77e5f6e9440fc92d6bb63b7635a3d-harness.json`). Unsandboxed `./init.sh` exited 0 (`verification/evidence/341b443661294f18b1d443011e407318-harness.json`). `git diff --check` and `python3 scripts/harness.py check` passed.
- `python3 scripts/harness.py verify-task p2-ingestion` exited 0 and promoted the task to verified. Harness: `verification/evidence/f10288cc8ebd436992f6364cb29d4c32-harness.json` (50 tests). Unit: `verification/evidence/6d31543c9fe04242a052d02e38a795ac-unit.json` (4/4). Integration: `verification/evidence/723fd090463b432c904b6cb25f338a1a-integration.json` (3/3). Isolation: `verification/evidence/adfeffa4766d42579d29b229bca17c08-isolation.json` (3/3).
- `python3 scripts/harness.py verify all` exited 3. Retrieval, generation, abstention, regression, and system remain unavailable and were not treated as passed.
- No blockers. Next eligible task: `p2-chunking`. A roadmap entry is not authorization to start it. Phase 2 stays in_progress until remaining children and the retrieval gate are done.

## Follow-up — 2026-09-16: p2-chunking

- Authorized and completed only `p2-chunking`; did not start indexing, retrieval, or retrieval evaluation. Added dependency-free `src/chunking.py` with configurable fixed and separator-aware recursive strategies, chunk size and overlap. Chunks preserve ingestion metadata plus section/page references, stable zero-based position, and absolute character offsets.
- Extended unit, integration, and isolation suites for fixed overlap, recursive boundaries, section/page separation, invalid configuration, progress when a natural boundary is shorter than overlap, real corpus ingestion-to-chunking, and overlapping cross-seller document IDs. Updated README and architecture status.
- Startup `./init.sh`, `git diff --check`, and `python3 scripts/harness.py check` passed. An initial integration/isolation run exposed a non-advancing recursive overlap cursor; the shared loop was fixed and a regression case added before promotion.
- `python3 scripts/harness.py verify-task p2-chunking` exited 0 and promoted the task to verified. Harness evidence: `verification/evidence/2864b97f66b9419cbfcc2a2e2af25522-harness.json`. Unit: `verification/evidence/26cf52276d814a44ab4b7ffe00d2cc1c-unit.json` (8/8). Integration: `verification/evidence/9c69fb1e945c44d7ac10e355d6003be6-integration.json` (4/4). Isolation: `verification/evidence/ce0c2b8036644655b69441e70c528052-isolation.json` (4/4).
- `python3 scripts/harness.py verify all` exited 3. Harness, unit, integration, dataset, and isolation passed; retrieval, generation, abstention, regression, and system remained unavailable and were not counted as passed.
- No blocker for `p2-chunking`. Next eligible task is `p2-indexing`; it remains unauthorized. Phase 2 stays in progress until all remaining children and the retrieval gate are verified.

## Follow-up — 2026-09-17: p2-indexing

- Authorized and completed only `p2-indexing`; did not start dense retrieval or retrieval evaluation. Added `src/indexing.py` with deterministic, unit-normalized feature-hashing embeddings and seller-scoped SQLite chunk storage. Stored records retain text, source metadata, stable seller-scoped chunk IDs, embedding model, and dimensions. The public inspection path always requires `seller_id`; mixed-seller batches are rejected before any write.
- Extended unit, integration, and isolation suites for deterministic/configurable embeddings, metadata persistence, the complete ingestion → chunking → indexing corpus path, overlapping cross-seller document IDs, filtered shared-index reads, and atomic rejection of mixed-seller writes. Updated README, architecture, and evaluation boundary documentation. No dependency, provider, top-K search, lifecycle operation, or evaluation runner was added.
- Startup `./init.sh` passed before implementation (`verification/evidence/546d58700657416c848705780175b3f4-harness.json`) and after implementation (`verification/evidence/e2cef89c182e440ea4eee9f842e44466-harness.json`). `git diff --check`, static compilation, and `python3 scripts/harness.py check` passed.
- `python3 scripts/harness.py verify-task p2-indexing` exited 0 and promoted the task to verified. Harness: `verification/evidence/47fcb83f21474475ba6a77da77a68d9e-harness.json` (50 tests). Unit: `verification/evidence/f17f11b3a0a24d68828866d6e00a08a5-unit.json` (11/11). Integration: `verification/evidence/db771e7e5d544f8c8f7a63cbb2cde795-integration.json` (5/5). Isolation: `verification/evidence/accd3213269641f4bad464fe12c580ad-isolation.json` (6/6).
- `python3 scripts/harness.py verify all` exited 3. Harness, unit, integration, dataset, and isolation passed; retrieval, generation, abstention, regression, and system remained unavailable and were not counted as passed. Evidence was recorded under `verification/evidence/`.
- No blocker for `p2-indexing`. Next eligible task is `p2-retrieval`; it remains unauthorized. Phase 2 stays in progress until retrieval, retrieval evaluation, and phase gates are verified.

## Follow-up — 2026-09-17: p2-retrieval

- Authorized and completed only `p2-retrieval`; did not start retrieval evaluation or any downstream task. Added dense cosine-ranked top-K retrieval to the existing dependency-free index. Retrieval requires `seller_id`, embeds the query with the index configuration, returns chunk text/source metadata plus score, omits stored vectors, and applies a deterministic chunk-ID tie break.
- Extended unit, integration, and isolation suites for ranking/top-K/input behavior, the real corpus ingestion → chunking → indexing → retrieval path, and shared-index seller isolation with conflicting return policies. Updated README, architecture, and evaluation-boundary documentation.
- Startup `./init.sh` passed before implementation (`verification/evidence/c29101335c1f4f5f9fa9e0158270a7c7-harness.json`) and after implementation (`verification/evidence/180178a395524aafb7c431ffdc79fba2-harness.json`). An initial unit run failed because its artificial 32-dimensional fixture produced a hash collision (`verification/evidence/5ab0e15b9e944f808e5b2d2edaebcbf5-unit.json`); the test was corrected to exercise the normal 256-dimensional configuration, then unit, integration, and isolation passed. `git diff --check` and `python3 scripts/harness.py check` passed.
- `python3 scripts/harness.py verify-task p2-retrieval` exited 0 and promoted the task to verified. Harness: `verification/evidence/8f6b51588d1e45b68014d13105e218aa-harness.json` (50 tests). Unit: `verification/evidence/31f2a79cef8244589f936ac6a1d23380-unit.json` (13/13). Integration: `verification/evidence/b5719994267d4d3f8c7a0fd3b30ca57a-integration.json` (6/6). Isolation: `verification/evidence/be7512fcfdff42b6af838eb211e79f50-isolation.json` (7/7).
- `python3 scripts/harness.py verify all` exited 3. Harness, unit, integration, dataset, and isolation passed; retrieval evaluation, generation, abstention, regression, and system remained unavailable and were not counted as passed. Evidence is under `verification/evidence/`.
- No blocker for `p2-retrieval`. Next eligible task is `p2-retrieval-evaluation`; it remains unauthorized. Phase 2 stays in progress until that child and the phase retrieval gate are verified.

## Follow-up — 2026-09-17: p2-retrieval-evaluation

- Authorized and completed only `p2-retrieval-evaluation`; did not close Phase 2 or start generation/downstream work. Added the standard-library retrieval evaluator, retrieval gate wiring, four evaluator checks, harness availability/negative checks, and the pinned per-case report `evals/reports/retrieval-baseline-v1.json`.
- The evaluator runs all 40 fixed cases through ingestion → recursive chunking (1000 characters, 100 overlap) → 256-dimensional feature-hashing embeddings → shared SQLite indexing → seller-scoped dense top-10 retrieval. Exact seller/document/version/section identities grade Recall@5 and MRR@10. All cases execute; the one case without expected evidence is reported but excluded from both metric denominators.
- Initial dense baseline: Recall@5 `0.594017094017094`; MRR@10 `0.4974358974358974`; 39 graded cases; 40/40 executed; 0 skipped; 0 errors; 0 cross-seller results; 62 indexed chunks. The acceptance policy certifies complete reproducible measurement without inventing a first-baseline quality floor.
- Startup `./init.sh` initially exposed one stale harness assertion that still expected retrieval to be unavailable (`verification/evidence/646b4286e98c44d09f0b8b0a16b51915-harness.json`). After updating that expectation, `./init.sh` passed 52 harness tests (`verification/evidence/70316017df9d4f638345920ee6160764-harness.json`). `git diff --check` and `python3 scripts/harness.py check` passed.
- `python3 scripts/harness.py verify-task p2-retrieval-evaluation` exited 0 and promoted the task to verified. Harness: `verification/evidence/4d290ed9b1854f8f80d649ff3fbf1650-harness.json`; dataset: `verification/evidence/c0b4ef00167c4cf886e48695961256f3-dataset.json`; retrieval: `verification/evidence/8d9862ce51a24d34b77e8555a2f83c0a-retrieval.json`; isolation: `verification/evidence/155e78231fd84dd4815fb5746f677a8e-isolation.json`.
- `python3 scripts/harness.py verify all` exited 3. Harness, unit, integration, dataset, retrieval, and isolation passed; generation, abstention, regression, and system remained unavailable and were not counted as passed.
- No blocker. All Phase 2 children are verified. Next eligible action is Phase 2 closure: set `phase-2` to implemented and run `python3 scripts/harness.py verify-task phase-2` only with authorization. After Phase 2 is verified, `p3-generation` becomes the next leaf task.

## Follow-up — 2026-09-17: repository-local Python environment

- Authorized and completed only the bounded `p2-local-venv` foundation task in `/home/liu/Code/Projects/rag-based-chatbox`. Added the task under Phase 2, reopened and reverified Phase 2, and did not change retrieval behavior, architecture, the pinned baseline, or any Phase 3 work.
- `./init.sh` now creates the git-ignored `.venv`, checks the repository-supported Python 3.10+ constraint, installs the checked-in `requirements.txt`, and runs the harness through `.venv/bin/python`. The current Phase 2 application uses only the standard library, so `requirements.txt` intentionally contains no third-party packages. The new environment used Python 3.14.4; `pip freeze --all` reported only `pip==25.1.1`.
- Confirmed the interpreter before verification: `/home/liu/Code/Projects/rag-based-chatbox/.venv/bin/python`, with `sys.prefix` inside `.venv` and a distinct `/usr` base prefix. Updated repository setup, test, evaluation and task-view commands to use that interpreter.
- `.venv/bin/python scripts/harness.py verify-task p2-local-venv` exited 0. Fresh local-environment evidence: `verification/evidence/8869dab76125450f84d30e8ebfe9eec2-harness.json`, `verification/evidence/e1f4a5d711fe4fe7990c6310291b3741-unit.json`, `verification/evidence/ccfb852bba054b0180a5e6a4006b1cad-integration.json`, `verification/evidence/2677f74bed83489f8abf243aa8e412d8-dataset.json`, `verification/evidence/1c182ec847fe43039b583a715067bedc-retrieval.json`, and `verification/evidence/52a1eaec46e34602a0d42aa09eeed93b-isolation.json`.
- `.venv/bin/python scripts/harness.py verify-task phase-2` exited 0 and restored Phase 2 to verified. Fresh phase evidence: `verification/evidence/36d7c36fc9df44d2bd57a53899ac84c4-harness.json`, `verification/evidence/313f54d8791c4b2785d70860512da505-unit.json`, `verification/evidence/b2a06042f0a9492388aac77f40ffae6a-integration.json`, `verification/evidence/694666f96b904751959bbdf303194eeb-dataset.json`, `verification/evidence/68d0f575980d41c08c46b0e5300151ed-retrieval.json`, and `verification/evidence/c5ad5077180e41749f44f5b382f6e9f3-isolation.json`.
- Baseline comparison was exact: Recall@5 remained `0.594017094017094`; MRR@10 remained `0.4974358974358974`; 39 graded and 1 ungraded case; 40/40 executed, 0 skipped, 0 failed, 62 indexed chunks; error rate `0.0`; seller leakage `0`; no failures. The existing `evals/reports/retrieval-baseline-v1.json` was preserved unchanged. Unit 13/13, integration 6/6, and isolation 7/7 passed.
- No blocker or downgrade. Phase 2 remains verified. Stop here; Phase 3 remains unauthorized.

## Follow-up — 2026-09-18: Phase 3 local-generation decision

- Authorized only to persist the selected Phase 3 implementation decisions in the harness; did not open Phase 3, implement generation, add dependencies or change the verified retrieval baseline.
- Added ADR `docs/decisions/0003-phase-3-local-generation.md`: local Ollama `qwen2.5:1.5b-instruct`, native `/api/chat`, standard-library HTTP/JSON, top-five evidence IDs, schema-constrained output, `stream=false`, `temperature=0`, `num_ctx=8192`, and `num_predict=384`. Citation metadata remains trusted application output, and `feature-hashing-v1` remains the embedding model.
- Extended Phase 3 task acceptance criteria and added a harness regression test so later sessions preserve the model/runtime, retrieval boundary, citation mapping and real-service evaluation requirements. Updated architecture, evaluation, development guidance and handoff.
- Local inspection found Ollama client 0.34.1 and installed model ID `65ec06548149` (986 MB); the future evaluator must record the actual resolved artifact rather than hard-code this observed machine state.
- Grader technology and numerical generation-quality thresholds remain a required decision before `p3-generation-evaluation` acceptance. Phase 3 implementation remains unauthorized.
- Verification passed: `.venv/bin/python scripts/harness.py check`; direct harness suite 53/53; `git diff --check`; post-change `./init.sh` with evidence `verification/evidence/f9c8d8b75ed74e47a4fc16bd49e21641-harness.json`. Status still reports `phase-3` and `p3-generation` as `not_started`.

## Follow-up — 2026-09-18: p3-generation

- Opened Phase 3 and completed only `p3-generation`; did not implement citation rendering or generation evaluation. Added `src/generation.py` with the fixed native Ollama `/api/chat` contract for `qwen2.5:1.5b-instruct`, top-five labeled evidence chunks, schema-constrained JSON, `stream=false`, `temperature=0`, `num_ctx=8192`, and `num_predict=384`.
- The standard-library generation boundary validates seller identity and non-empty evidence before transport, rejects malformed output and unknown/duplicate evidence IDs, and keeps `feature-hashing-v1` plus the pinned retrieval baseline unchanged. Implementation tests use an injected fake transport and do not count as product generation evaluation.
- Added three unit checks, one real retrieval-to-generation integration check, and one shared-index cross-seller rejection check. Updated README and architecture status. No dependency, cloud credential, provider SDK, citation renderer, evaluator or Phase 4 behavior was added.
- First implementation-gate run passed: unit `verification/evidence/fa429fa533474cb29f79154e3c57d9a0-unit.json`, integration `verification/evidence/ed8ef97738354c09840ab6c7cc4038a5-integration.json`, isolation `verification/evidence/a2d6905ce391419592e78b2451f5b0f4-isolation.json`. Post-change `./init.sh` passed with `verification/evidence/c330c06d65ee44b1b9cda23a5989aa23-harness.json`.
- `.venv/bin/python scripts/harness.py verify-task p3-generation` exited 0 and promoted the task to verified. Evidence: harness `verification/evidence/4a9a3a6e87794079a38aec645087f4d9-harness.json`; unit `verification/evidence/e3a479586aa94c97814de1a00bc91d51-unit.json` (16/16); integration `verification/evidence/0d4f4ae95c9e4bf99776fe2b5075d7df-integration.json` (7/7); isolation `verification/evidence/bb7558f4dde1495ea283f2b6a8bcbf52-isolation.json` (8/8).
- No blocker. `p3-citations` is the next eligible child; Phase 3 remains in progress.

## Follow-up — 2026-09-18: p3-citations and Phase 3 stop

- Completed only `p3-citations`. The existing generation result now includes citations resolved from model-selected evidence IDs to trusted seller-scoped retrieval metadata. Citations include document name and section/page when available; unknown, duplicate and cross-seller evidence IDs are rejected. The model cannot supply or override citation metadata.
- First implementation-gate run passed: unit `verification/evidence/02bfe1d5356d42b889f7715a591d2103-unit.json`, integration `verification/evidence/9dd13923597346fca4064c466168660b-integration.json`, isolation `verification/evidence/929331e99ab54e089cb74b526c96af37-isolation.json`. Post-change `./init.sh` passed with `verification/evidence/3157ce310f0a4a4c9254bfc5f21a9b25-harness.json`.
- `.venv/bin/python scripts/harness.py verify-task p3-citations` exited 0 and promoted the task to verified. Evidence: harness `verification/evidence/0cfb7ac1659c45f8833fed37b9b1bfba-harness.json`; unit `verification/evidence/5fdc008b9b4145eaa1cf6415f8d2b04b-unit.json` (17/17); integration `verification/evidence/d0c530c609e84cdd8ee20aeb02f415f5-integration.json` (7/7); isolation `verification/evidence/b3d11ce0ff5e4783b4e7280a98dfd346-isolation.json` (8/8).
- Retrieval regression passed unchanged with `verification/evidence/37d6470e10c547a4addd957052ce889c-retrieval.json`: Recall@5 `0.594017094017094`, MRR@10 `0.4974358974358974`, 40/40 executed, 0 failed, 0 skipped, 0 cross-seller results and 0.0 error rate.
- Stopped before `p3-generation-evaluation` under the user-defined human-review conditions. Its acceptance criteria and ADR 0003 leave grader technology and numeric faithfulness/relevance/completeness/citation-correctness thresholds undecided. The task is blocked pending that explicit decision; generation, regression and system gates remain unavailable. Phase 3 remains in progress and unverified; Phase 4 was not started.
