# Architecture boundary

Status: seller-scoped document parsing and configurable fixed/recursive chunking are implemented in Python 3 standard library. Embeddings, vector storage, retrieval, generation and provider choices remain unimplemented. PROJECT_SPEC.md §§6–15, 27–29 are authoritative.

Seller-scoped ingestion: upload/direct text → parse/clean → configurable fixed or recursive chunks → embeddings → vector store. Current code stops after chunking: chunks retain seller/source metadata, section or page, stable position, and absolute character offsets. Isolation applies to every parse, corpus read, and chunk. The PDF extractor covers Latin text operators and FlateDecode streams, not CMaps, form XObjects or OCR.

Seller-scoped answering: query → dense top-K retrieval → evidence validation → generation → grounding validation → answer with citations, or safe abstention. Isolation applies to every document/index/retrieval operation from the baseline onward. Updates and deletions must eliminate stale influence after re-indexing completes.

The fixed dataset and evaluation runners form a separate measurement boundary: retrieval, generation/grounding, citation correctness, abstention, system metrics and regression comparisons. No optimization until the baseline is measurable. Advanced retrieval and initial non-goals remain governed by spec §§15–16, 23, 28, 30.

## Repository map
- Root: specification, agent routing, task state, progress and handoff.
- `scripts/harness.py`, `tests/harness/`: control-plane checks only.
- `scripts/validate_dataset.py`, `tests/dataset/`: dependency-free Phase 1 corpus and annotation validation, exposed through the dataset gate.
- `src/ingestion.py`: seller-scoped parse/clean for PDF, Markdown, TXT and direct text.
- `src/chunking.py`: dependency-free fixed and separator-aware recursive chunking with configurable size and overlap.
- `tests/unit/`, `tests/integration/`, `tests/isolation/`: ingestion and chunking implementation checks; later tasks extend these suites. They do not index or retrieve.
- `verification/evidence/`: generated command records, separate from future RAG evaluation reports.
- `docs/`: workflow, Definition of Done, evaluation contracts and decisions.
- `data/raw/`: versioned evaluation policy corpus (`eval-policy-corpus` v1) with seller-scoped documents and `corpus.json` identities.
- `evals/datasets/`: versioned evaluation questions (`eval-policy-questions` v1). Retrieval reports and remaining application paths are created with their real work.

Record significant choices in `docs/decisions/` when evidence requires them; do not select technologies merely to fill out an architecture document.
