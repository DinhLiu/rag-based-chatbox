# Repository Definition of Done

PROJECT_SPEC.md §25 controls product completion; §§17–24, 26 and 29 specify its evidence. A task is done only in `verified` state, with reproducible successful command records for the implemented snapshot.

For application features, require all of the following:
1. Acceptance criteria match the spec; deliverables and new behavior have relevant tests/evaluation cases.
2. Relevant unit and integration tests actually run and pass.
3. Required retrieval, generation/grounding/citation and abstention evaluations run on versioned fixtures.
4. Regression comparison identifies previously passing cases and reports no unacceptable regressions; inspect each failure.
5. Seller isolation and stale-document behavior are checked where data is accessed or changed.
6. Required docs, task state and handoff are updated, with commands, reports and input/configuration identity.

Unsupported confident answers are high-severity failures and block acceptance. Cross-seller leakage blocks acceptance. Do not suppress cases, lower acceptance bars or bless regressions to finish a task. Resolve ambiguity in numerical acceptance thresholds before the relevant evaluator can certify success; the spec defines metrics but does not supply numeric targets. Record agreed thresholds and grading method before measuring an optimization.

Phase-specific gates are in feature_list.json. Phase 1 closure needs dataset validation; corpus/annotation preparation children use harness-only workflow checks without claiming data quality, and p1-dataset-checks creates the validator and verifies the complete dataset; Phase 2 needs retrieval and isolation measurements; generation and abstention gates become applicable as those features are introduced. This stages verification without claiming the whole MVP is complete. Phase 0 only certifies the development harness via structural checks, static compilation and behavioral harness tests; it certifies no product behavior.

If checks cannot run, leave the task `implemented` or `blocked`, with the reason and next action. Manual review supplements external evidence; it cannot replace tests, metrics or evaluations. No empty suite, placeholder, mocked product success, missing report, or unavailable service counts as passed. Run `verify-task` to promote state; do not manually set `verified`.

Phases and tasks use the same schema with optional `parent` links. Child tasks must satisfy their own criteria and applicable gates; a phase additionally requires every child verified and its full phase gates passed. Adding a child or reopening failed work also reopens the phase; task decomposition cannot weaken product acceptance.

Implementation children run checks for currently implemented behavior. Full phase quality gates stay on the evaluation child and phase closure, so a downstream evaluator does not block its own prerequisites. See docs/DEVELOPMENT.md for runner ownership. A verified preparation child with only harness evidence does not establish product correctness or satisfy phase acceptance.
