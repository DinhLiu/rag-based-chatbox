# Architecture boundary

Status: seller-scoped parsing, configurable fixed/recursive chunking, deterministic feature-hashing embeddings, SQLite vector storage, dense top-K retrieval, retrieval baseline evaluation, evidence-grounded local Ollama generation, and trusted citation resolution are implemented in Python 3 standard library. Phase 3 quality evaluation remains unimplemented. PROJECT_SPEC.md §§6–15, 17–19, 21–24, 27–29 are authoritative.

Seller-scoped ingestion and retrieval: upload/direct text → parse/clean → configurable fixed or recursive chunks → deterministic unit-normalized feature-hashing embeddings → SQLite vector store → cosine-ranked top-K chunks. Stored records retain chunk text, complete source metadata, embedding model/dimensions, and seller-scoped stable chunk IDs. The indexing API rejects mixed-seller batches before writing; inspection and retrieval require a seller filter. Isolation applies to every parse, corpus read, chunk, index, and retrieval operation. The PDF extractor covers Latin text operators and FlateDecode streams, not CMaps, form XObjects or OCR.

Seller-scoped answering: query → dense top-K retrieval → evidence validation → generation → grounding validation → answer with citations, or safe abstention. Isolation applies to every document/index/retrieval operation from the baseline onward. Updates and deletions must eliminate stale influence after re-indexing completes.

The selected Phase 3 baseline uses local Ollama `qwen2.5:1.5b-instruct` through native `/api/chat`: top-five evidence IDs, schema-constrained JSON, no streaming, temperature 0, 8192-token context and 384 generated-token cap. The generation boundary rejects empty or cross-seller evidence before the request and rejects malformed or unknown evidence IDs in model output. It resolves model-selected IDs to document name and available section/page fields from the original seller-scoped retrieval records; the model cannot supply citation metadata. Standard-library HTTP/JSON is sufficient, so the baseline adds no provider SDK or multi-provider layer. This choice does not change the verified `feature-hashing-v1` embedding or retrieval baseline.

The fixed dataset and evaluation runners form a separate measurement boundary. Retrieval evaluation now runs the complete corpus through ingestion, recursive chunking, feature-hashing embeddings, shared SQLite indexing, and seller-scoped dense top-10 retrieval. Exact seller/document/version/section identities grade Recall@5 and MRR@10; its pinned report is the comparison point for later retrieval changes. Generation/grounding, citation correctness, abstention, system metrics and regression comparisons remain future boundaries. Advanced retrieval and initial non-goals remain governed by spec §§15–16, 23, 28, 30.

## Repository map
- Root: specification, agent routing, task state, progress and handoff.
- `scripts/harness.py`, `tests/harness/`: control-plane checks only.
- `scripts/validate_dataset.py`, `tests/dataset/`: dependency-free Phase 1 corpus and annotation validation, exposed through the dataset gate.
- `src/ingestion.py`: seller-scoped parse/clean for PDF, Markdown, TXT and direct text.
- `src/chunking.py`: dependency-free fixed and separator-aware recursive chunking with configurable size and overlap.
- `src/indexing.py`: dependency-free deterministic embeddings, seller-scoped SQLite chunk storage, and cosine-ranked dense top-K retrieval.
- `src/generation.py`: fixed local Ollama request contract and validated answer/evidence-ID output.
- `scripts/evaluate_retrieval.py`, `tests/retrieval/`: complete fixed-dataset retrieval evaluation and baseline reproducibility checks, exposed through the retrieval gate.
- `evals/reports/retrieval-baseline-v1.json`: pinned initial dense baseline with per-case evidence and metrics.
- `tests/unit/`, `tests/integration/`, `tests/isolation/`: ingestion-through-generation implementation checks; later tasks extend these suites.
- `verification/evidence/`: generated command records, separate from future RAG evaluation reports.
- `docs/`: workflow, Definition of Done, evaluation contracts and decisions.
- `data/raw/`: versioned evaluation policy corpus (`eval-policy-corpus` v1) with seller-scoped documents and `corpus.json` identities.
- `evals/datasets/`: versioned evaluation questions (`eval-policy-questions` v1). Retrieval reports and remaining application paths are created with their real work.

Record significant choices in `docs/decisions/` when evidence requires them; do not select technologies merely to fill out an architecture document.
