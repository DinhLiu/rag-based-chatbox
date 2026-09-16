# Evaluation contract (planned, not implemented)

Authority: PROJECT_SPEC.md §§17–24, 29. Evaluators, scores and an accepted baseline do not exist yet.

The versioned policy corpus is `eval-policy-corpus` version `1` under `data/raw/`. `data/raw/corpus.json` is the catalog. Each document is identified by `(seller_id, document_id, version)`. `document_id` may repeat across sellers; `seller_id` is required on every later read. `seller-aurora` is the primary evaluation seller. `seller-beacon` holds overlapping document IDs with different rules for isolation cases. Question files belong in `evals/datasets/` when that task is implemented.

Phase 1 still needs approximately 30–50 fixed cases, with query, expected_sources, expected_answer_points where answerable, and answerable labels. Follow the suggested distribution in §22 (40% simple, 20% paraphrased, 15% multi-policy, 15% unanswerable, 10% ambiguous/adversarial). Add stable case IDs, seller identity and source/version identity to make runs reproducible. Check annotations against the actual policy evidence; schema validity alone does not prove annotation correctness.

Measure retrieval Recall@5 and MRR@10. Generation evaluation covers faithfulness, answer relevance, citation correctness and completeness, including important policy conditions and accurate document name/section/page references. Evaluate abstention precision/recall and False Answer Rate, covering missing, low-relevance, incomplete, conflicting and out-of-scope evidence. Confident unsupported answers are high-severity failures. Include answerable cases to detect excessive refusal.

Isolation cases must exercise ingestion/document access/indexing/retrieval across at least two sellers, with misleadingly similar policies; tenant scoping is mandatory even before Phase 5. Lifecycle regression cases must verify deleted/replaced chunks no longer influence results after re-indexing. Trace coverage to spec §§5–13. Preserve previously passing cases unless the specification changes.

Machine-readable application reports must include:
- Run ID/time, command, source revision/content identity, dataset and corpus versions/hashes, configuration (chunking, model, prompts, top-K, thresholds and seed where supported).
- Count of collected, executed, skipped and failed cases; per-case results with expected/actual evidence and answer/claim/citation judgments and failure reasons.
- Aggregate metrics with denominators, grading method/version and predeclared acceptance policy; reject empty or wholly skipped runs.
- Retrieval, end-to-end and LLM latency; token usage, cost per query and error rate (spec §21). Missing observations remain unavailable, not zero.
- Baseline report ID with comparable corpus/dataset/configuration, per-case regressions, metric deltas, latency/cost impact and final pass/fail/unavailable status.

Store real datasets under `evals/datasets/` and reports under `evals/reports/` when implemented. Pin the first measured dense baseline; an initial baseline run establishes a reference and must not pretend to compare against a nonexistent one. Subsequent meaningful changes require a comparable reference. Version intentional corpus/dataset changes and explain comparisons; do not silently overwrite the baseline.

Before optimization, record an experiment in `docs/experiments/`: experiment ID, change, hypothesis, baseline metrics, new metrics, latency impact, cost impact, conclusion and linked raw reports (spec §23). Hybrid search, reranking, query rewriting and other advanced techniques remain gated by measured baseline evidence and demonstrated benefit. Mandatory seller filtering is an isolation invariant, not an optional retrieval enhancement.

Grading implementation, application technologies and numeric acceptance targets remain undecided. Resolve them with recorded evidence/decisions during the relevant phase; do not invent scores or thresholds in the harness.
