# 0003 — Local Ollama baseline generation

Status: accepted and implemented for Phase 3, updated 2026-09-18.

Context: Phase 2 is verified with `feature-hashing-v1` embeddings, SQLite storage and seller-scoped dense retrieval. Phase 3 needs a reproducible generation runtime without sending seller policy text to a cloud provider. The selected model is already present locally as Ollama tag `qwen2.5:7b-instruct-q4_K_M`; the observed local artifact is ID `845dbda0ea48`, Q4_K_M, approximately 4.7 GB. The runtime report must record the artifact actually used rather than assuming this observed ID forever.

Decision: use the native local Ollama `POST /api/chat` endpoint at configurable base URL `http://127.0.0.1:11434`. Use model tag `qwen2.5:7b-instruct-q4_K_M`, `stream: false`, `temperature: 0`, `num_ctx: 8192`, `num_predict: 384`, and a JSON Schema in `format`. Supply the first five retrieved chunks as delimited evidence IDs `E1`–`E5`. The model returns only an answer and referenced evidence IDs; application code resolves document name, section and page from trusted retrieved metadata. Use the same tag for the Phase 3 semantic judge. Use Python's standard-library HTTP and JSON support; do not add an Ollama SDK, Pydantic, a cloud credential or a multi-provider abstraction for this one-provider baseline.

Retrieval boundary: this decision does not replace the Phase 2 embedding model. Keep `feature-hashing-v1`, its 256 dimensions, SQLite index and pinned retrieval baseline unchanged during Phase 3. Any embedding change is a separate retrieval experiment that reopens and revalidates affected Phase 2 results.

Evaluation boundary: generation evaluation must report the Ollama version, model tag and resolved artifact identity, all generation options, prompt/schema version, durations and token counts. Measure generation with both annotated gold evidence and actual end-to-end retrieved evidence so retrieval misses are not misdiagnosed as generation failures. A missing Ollama service or model is unavailable, never a mocked pass. Unit tests may use an injected fake transport, but successful product evaluation must exercise the selected local model. The grading technology and numerical faithfulness/relevance/completeness thresholds remain unresolved and must be recorded before `p3-generation-evaluation` can be accepted.

Alternatives: a hosted model would add credentials, cost and external data transfer. A separate smaller generator would reduce runtime but would make the architecture depend on a second model. Using Qwen as an embedding model would conflate the verified retrieval baseline with generation work.

Consequences: no per-request provider charge, seller evidence remains local, and both generation and semantic grading use one model artifact. The 7B quantized model needs more memory and latency than a smaller generator; evaluation, not manual examples, decides whether it meets grounding and completeness targets.
