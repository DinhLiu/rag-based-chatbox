# 0002 — Failed rechecks preserve valid state and bound gate runtime

Status: accepted for the authorized harness repair, 2026-09-16.

Context: a failed upstream recheck could leave active/verified dependents violating the prerequisite invariant and prevent even recovery commands. Gate subprocesses also had no execution deadline.

Decision: keep the existing five states. The failed target becomes implemented. In-progress, implemented and verified dependents with unverified prerequisites become blocked with an explicit revalidation reason; active evidence references are cleared. Reopen verified parents with unfinished children, and propagate until all inherited/direct dependencies and parent completion constraints hold. Keep historical report files. Validate the complete candidate state before saving it. Resume and reverify dependents explicitly after upstream recovery; never restore old verification automatically.

Alternatives: downgrading all dependents to implemented still violates the current prerequisite rule. Adding needs_revalidation would broaden the schema unnecessarily. Relaxing the dependency invariant could falsely permit work on unverified prerequisites.

Timeouts: finite per-gate budgets in a standard-library subprocess runner. Timeout is a failed check (exit 1) with budget, timeout flag, partial output and diagnostic recorded in evidence. It is not the unavailable placeholder (exit 3). The direct runner process is killed/waited on by subprocess.run; future runners owning child processes must clean them up.

Deferred: task-scoped input hashes and stale-evidence checks, transition CLI/history, concurrent writes, authorization state, stricter blocked-parent semantics and validation refactoring. The current request prioritizes recovery correctness and deadlines; these later changes remain separate work. No application implementation or external dependencies are introduced.
