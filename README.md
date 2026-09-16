# RAG-Based Customer Policy Chatbot

Development harness plus a versioned evaluation policy corpus under `data/raw/`. No RAG pipeline, evaluation questions, application runners or technology stack has been implemented or selected.

Start with [AGENTS.md](AGENTS.md), read the authoritative [PROJECT_SPEC.md](PROJECT_SPEC.md), then run:

```sh
./init.sh
```

Requires Python 3.10+ and a POSIX shell; uses only the standard library, installs nothing, needs no credentials or network. Git is used for inspecting changes. Node.js is only needed to rerun the external harness-creator skill validator.

[Development workflow](docs/DEVELOPMENT.md) · [Task state](feature_list.json) · [Handoff](session-handoff.md) · [Definition of Done](docs/DEFINITION_OF_DONE.md) · [Architecture](ARCHITECTURE.md) · [Evaluation contract](docs/EVALUATION.md)

`python3 scripts/harness.py verify all` intentionally exits 3 while application checks are unavailable. This is not a passing application build.

The existing task schema supports optional `parent` links (for example, `p2-ingestion` → `phase-2`). Work on bounded child tasks; verify phases only after every child and the phase gates pass. CLI usage errors exit 2, separately from unavailable verification (3).

For a compact session view, run `python3 scripts/harness.py status`, then `python3 scripts/harness.py task <id>`. These commands read the canonical tracker without changing state or generating evidence. Implementation tasks and full phase quality evaluation use staged gates so downstream evaluators do not block their own prerequisites.
