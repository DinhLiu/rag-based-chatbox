# Evaluation contract and dataset validation

Authority: PROJECT_SPEC.md §§17–24, 29. Phase 1 dataset validation is implemented; retrieval/generation evaluators, scores, and an accepted baseline do not exist yet.

The versioned policy corpus is `eval-policy-corpus` version `1` under `data/raw/`. `data/raw/corpus.json` is the catalog. Each document is identified by `(seller_id, document_id, version)`. `document_id` may repeat across sellers; `seller_id` is required on every later read. `seller-aurora` is the primary evaluation seller. `seller-beacon` holds overlapping document IDs with different rules for isolation cases.

The versioned question set is `eval-policy-questions` version `1` at `evals/datasets/eval-policy-questions-v1.json`. It contains 40 cases (16 simple, 8 paraphrased, 6 multi-policy, 6 unanswerable, 4 ambiguous/adversarial) with query, answerable labels, expected_sources, expected_source_identity (`seller_id`, `document_id`, `version`, section), and expected_answer_points on answerable cases. `python3 scripts/harness.py verify dataset` checks fixed version binding, seller-scoped document identities and paths, document headers and sections, case/schema integrity, exact distribution, source annotation consistency, and meaningful-token support for answer points in the cited sections. It rejects empty or skipped datasets and runs mutation tests before validating the real fixtures.

Measure retrieval Recall@5 and MRR@10. Generation evaluation covers faithfulness, answer relevance, citation correctness and completeness, including important policy conditions and accurate document name/section/page references. Evaluate abstention precision/recall and False Answer Rate, covering missing, low-relevance, incomplete, conflicting and out-of-scope evidence. Confident unsupported answers are high-severity failures. Include answerable cases to detect excessive refusal.

Isolation cases must exercise ingestion/document access/indexing/retrieval across at least two sellers, with misleadingly similar policies; tenant scoping is mandatory even before Phase 5. Implementation checks now cover seller-scoped parse, corpus reads, chunks, mixed-seller write rejection, and filtered index inspection; retrieval isolation remains a later Phase 2 task. Lifecycle regression cases must verify deleted/replaced chunks no longer influence results after re-indexing. Trace coverage to spec §§5–13. Preserve previously passing cases unless the specification changes.

Machine-readable application reports must include:
- Run ID/time, command, source revision/content identity, dataset and corpus versions/hashes, configuration (chunking, model, prompts, top-K, thresholds and seed where supported).
- Count of collected, executed, skipped and failed cases; per-case results with expected/actual evidence and answer/claim/citation judgments and failure reasons.
- Aggregate metrics with denominators, grading method/version and predeclared acceptance policy; reject empty or wholly skipped runs.
- Retrieval, end-to-end and LLM latency; token usage, cost per query and error rate (spec §21). Missing observations remain unavailable, not zero.
- Baseline report ID with comparable corpus/dataset/configuration, per-case regressions, metric deltas, latency/cost impact and final pass/fail/unavailable status.

Question cases live under `evals/datasets/`. Store evaluation reports under `evals/reports/` when that runner is implemented. Pin the first measured dense baseline; an initial baseline run establishes a reference and must not pretend to compare against a nonexistent one. Subsequent meaningful changes require a comparable reference. Version intentional corpus/dataset changes and explain comparisons; do not silently overwrite the baseline.

Before optimization, record an experiment in `docs/experiments/`: experiment ID, change, hypothesis, baseline metrics, new metrics, latency impact, cost impact, conclusion and linked raw reports (spec §23). Hybrid search, reranking, query rewriting and other advanced techniques remain gated by measured baseline evidence and demonstrated benefit. Mandatory seller filtering is an isolation invariant, not an optional retrieval enhancement.

Grading implementation, application technologies and numeric acceptance targets remain undecided. Resolve them with recorded evidence/decisions during the relevant phase; do not invent scores or thresholds in the harness.
