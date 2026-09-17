# RAG-Based Customer Policy Chatbot

Development harness plus a versioned evaluation policy corpus under `data/raw/`, versioned evaluation questions under `evals/datasets/`, a dataset validator, seller-scoped document parsing, configurable fixed/recursive chunking, deterministic embeddings, SQLite chunk indexing, seller-scoped dense top-K retrieval, and a reproducible retrieval baseline. Generation and later evaluation runners are not implemented.

Start with [AGENTS.md](AGENTS.md), read the authoritative [PROJECT_SPEC.md](PROJECT_SPEC.md), then run:

```sh
./init.sh
```

Requires Python 3.10+ and a POSIX shell. `./init.sh` creates the git-ignored `.venv`, installs the application dependency set from `requirements.txt`, and runs the harness with `.venv/bin/python`. Phase 2 uses only the Python standard library, so the dependency file intentionally contains no third-party packages and setup needs no credentials or network. The requirement is enforced by the existing bootstrap check; the local migration was revalidated with Python 3.14.4. Git is used for inspecting changes. Node.js is only needed to rerun the external harness-creator skill validator.

[Development workflow](docs/DEVELOPMENT.md) · [Task state](feature_list.json) · [Handoff](session-handoff.md) · [Definition of Done](docs/DEFINITION_OF_DONE.md) · [Architecture](ARCHITECTURE.md) · [Evaluation contract](docs/EVALUATION.md)

`.venv/bin/python scripts/harness.py verify dataset` validates the complete Phase 1 corpus and annotations. `verify unit`, `verify integration`, and `verify isolation` run ingestion-through-retrieval implementation checks. `verify retrieval` reproduces the pinned Recall@5 and MRR@10 baseline in `evals/reports/retrieval-baseline-v1.json`. `verify all` still exits 3 while generation, abstention, regression, and system checks are unavailable; this is not a passing application build.

The existing task schema supports optional `parent` links (for example, `p2-ingestion` → `phase-2`). Work on bounded child tasks; verify phases only after every child and the phase gates pass. CLI usage errors exit 2, separately from unavailable verification (3).

For a compact session view, run `.venv/bin/python scripts/harness.py status`, then `.venv/bin/python scripts/harness.py task <id>`. These commands read the canonical tracker without changing state or generating evidence. Implementation tasks and full phase quality evaluation use staged gates so downstream evaluators do not block their own prerequisites.
