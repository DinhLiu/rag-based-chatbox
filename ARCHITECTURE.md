# Architecture boundary

Status: planned product architecture, no implemented application components. PROJECT_SPEC.md §§6–15, 27–29 are authoritative. Providers, application language, frameworks, embedding model, vector store and deployment platform remain undecided.

Seller-scoped ingestion: upload/direct text → parse/clean → configurable fixed or recursive chunks → embeddings → vector store. Preserve available source, position, seller and version metadata for citations and lifecycle operations.

Seller-scoped answering: query → dense top-K retrieval → evidence validation → generation → grounding validation → answer with citations, or safe abstention. Isolation applies to every document/index/retrieval operation from the baseline onward. Updates and deletions must eliminate stale influence after re-indexing completes.

The fixed dataset and evaluation runners form a separate measurement boundary: retrieval, generation/grounding, citation correctness, abstention, system metrics and regression comparisons. No optimization until the baseline is measurable. Advanced retrieval and initial non-goals remain governed by spec §§15–16, 23, 28, 30.

## Repository map
- Root: specification, agent routing, task state, progress and handoff.
- `scripts/harness.py`, `tests/harness/`: control-plane checks only.
- `verification/evidence/`: generated command records, separate from future RAG evaluation reports.
- `docs/`: workflow, Definition of Done, evaluation contracts and decisions.
- Future application paths follow spec §27 (`src/`, application `tests/`, `evals/`, `data/`); create them with real work rather than empty application scaffolding.

Record significant choices in `docs/decisions/` when evidence requires them; do not select technologies merely to fill out an architecture document.
