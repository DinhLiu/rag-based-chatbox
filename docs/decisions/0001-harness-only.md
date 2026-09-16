# 0001 — Dependency-free development control plane

Status: accepted for initial harness, 2026-09-16.

Context: PROJECT_SPEC.md §§25–28 and the current request require persistent state and external verification without implementing RAG or selecting application dependencies.

Decision: use a small Python 3.10+ standard-library command runner, JSON task state and Markdown routing/handoff. Python is a harness runtime only; it does not choose the application stack. Keep application gates explicitly unavailable until real runners exist. Separate harness evidence from future evaluation reports.

Alternatives: package-manager scripts would prematurely select an application ecosystem; prose-only completion would lack executable failure gates.

Consequences: no install or network required; Node is optional for external skill validation. Gate integrations and application grading policies remain future work. Repository review remains necessary because local evidence is not a cryptographic trust service.
