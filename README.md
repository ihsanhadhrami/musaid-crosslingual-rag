# Musaid (مساعد)

Cross-lingual support RAG that answers Arabic (MSA, Gulf, Levantine/Egyptian, code-switched, Arabizi) and English questions from an English-only knowledge base, with a public benchmark.

> **Status: Phase 0 (setup).** Results, demo and benchmark links will appear here as phases ship. Full plan: [project-1-bilingual-support-rag.md](project-1-bilingual-support-rag.md).

## Run locally

Requirements: Docker (with about 4 GB of RAM free) and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env          # dev defaults; edit if ports clash
docker compose up -d          # Postgres+pgvector, Langfuse
uv sync                       # Python 3.12 env + deps
uv run pre-commit install     # git hooks
uv run pytest                 # unit + integration tests
```

| Service | URL | Notes |
|---|---|---|
| App DB (pgvector) | `localhost:15432` | db/user/password: `musaid` (port set by `POSTGRES_PORT`) |
| Langfuse UI | http://localhost:3000 | Login: `admin@musaid.local` / `musaid-admin` |
| MinIO console | http://localhost:9091 | Langfuse blob storage |

To run only the tests that don't need Docker: `uv run pytest -m "not integration"`.

## Repository layout

```
src/musaid/      lang · translate · ingest · retrieval · generation · api · observability
eval/            retrieval/answer eval harness; results/ holds one JSON per run
data/            kb · glossary · eval · sanity_check (gitignored)
docs/            DECISIONS.md (ADRs), style guide, annotation guide, results
frontend/        React + Tailwind (Phase 7)
```

## Scope

Out of scope on purpose: Arabic-language KB documents, fine-tuning, agents, voice, and account actions. See §2 of the plan.
