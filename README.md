# Musaid (مساعد)

Cross-lingual support RAG that answers Arabic (MSA, Gulf, Levantine/Egyptian, code-switched, Arabizi) and English questions from an English-only knowledge base, with a public benchmark.

> **Status: Phase 2 (glossary and benchmark).** The KB is frozen at 354 articles and 600 chunks ([docs/KB_STATS.md](docs/KB_STATS.md)). The glossary has 153 entries, and 462 evaluation queries are drafted ([docs/EVAL_STATS.md](docs/EVAL_STATS.md)); human verification is in progress and the test set isn't locked yet. Full plan: [project-1-bilingual-support-rag.md](project-1-bilingual-support-rag.md).

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

## Benchmark tools

```bash
uv run python -m musaid.glossary.build              # validate the glossary, write glossary.jsonl
uv run python -m musaid.benchmark.build             # validate queries, write queries/dev/test.jsonl
uv run python -m musaid.benchmark.search "refund"   # find candidate gold chunks
uv run python -m musaid.benchmark.review            # review sheet with a competitor check
uv run python -m musaid.benchmark.split assign      # dev/test split (ADR-012); `lock` after review
uv run python -m musaid.benchmark.agreement score   # second-annotator agreement
```

Labeling rules are in [docs/ANNOTATION.md](docs/ANNOTATION.md).

## Repository layout

```
src/musaid/      lang · translate · ingest · retrieval · generation · api · observability
eval/            retrieval/answer eval harness; results/ holds one JSON per run
data/            kb · glossary · eval · sanity_check (gitignored)
docs/            DECISIONS.md (ADRs), style guide, annotation guide, results
frontend/        React + Tailwind (Phase 7)
```

## Known limitations

- **Smaller KB than the spec's target.** The knowledge base is 354 articles and 600 chunks, below the 1,000–3,000 in the plan (ADR-008).
- **Mostly LLM-drafted text.** Only 40 of the 200 help articles are rewritten by hand (ADR-007). Results are reported separately for rewritten and draft gold articles.
- **LLM-drafted, human-verified queries.** The evaluation queries were drafted with an LLM from customer intents, then checked and corrected by a native Arabic speaker. The same author wrote the glossary, so query wording may overlap with glossary forms; that overlap is measured before glossary results are reported.

## Scope

Out of scope on purpose: Arabic-language KB documents, fine-tuning, agents, voice, and account actions. See §2 of the plan.
