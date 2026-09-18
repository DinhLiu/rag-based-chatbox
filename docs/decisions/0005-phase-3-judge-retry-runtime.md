# 0005 — Phase 3 local judge retry and runtime budget

Status: accepted, 2026-09-18.

Context: the atomic calibration recorded in ADR 0004 completed all 62 examples but did not meet the accepted agreement, kappa, unsupported-precision or unsupported-recall floors. The generation-evaluation task was blocked pending a human decision about the judge and runtime budget.

Decision: continue with the local Ollama judge tag `qwen2.5:7b-instruct-q4_K_M` and increase the generation, regression and system gate budgets from 1800 seconds to 2400 seconds. This exact judge tag was already used by the latest calibration attempts, so this decision authorizes a bounded retry with more wall-clock budget; it does not claim a new model artifact or erase the failed calibration evidence. The evaluator must record the resolved Ollama artifact in every run.

The atomic support/citation and availability/coverage prompts, fixed 62-example calibration set, 20-example holdout and all quality thresholds from ADR 0004 remain unchanged. A longer timeout is a runner budget, not a product-latency target and not evidence that the judge is accepted. The task may proceed only through fresh calibration and, if calibration passes, a fresh baseline run.

Alternatives: changing to another local or cloud judge was not selected. Lowering calibration or generation-quality thresholds, deleting cases, or accepting prior failed reports was rejected because it would weaken the agreed grounding safeguards.

Consequences: `p3-generation-evaluation` may resume from blocked to in progress. The harness implementation and timeout regression tests must be updated to 2400 seconds before the real-service retry. If the unchanged 7B judge again misses the accepted calibration floors, stop and return to human review rather than tuning thresholds or claiming a baseline.
