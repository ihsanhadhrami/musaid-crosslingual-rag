# Architecture Decision Records

One short record per major choice. Format: context → decision → consequences.
Status is one of: Accepted, Superseded by ADR-N, Proposed.

---

## ADR-001: Repo layout and tooling

**Status:** Accepted (Phase 0)

**Context:** This is a one-person project that must be reproducible by reviewers and hiring managers.

**Decision:**
- Python 3.12, managed by `uv`; `uv.lock` is committed, and CI installs with `uv sync --locked`.
- `src/` layout (`src/musaid`), so tests run against the installed package and never against stray modules in the working directory.
- `ruff` handles both lint and formatting. `pytest` runs the tests. `pre-commit` runs the same checks locally.
- Tests marked `integration` need the Docker stack. Plain `pytest -m "not integration"` runs anywhere.

**Consequences:** One tool each for environment, lint and tests. Python is pinned to 3.12 because CAMeL Tools and parts of the ML stack lag behind new Python releases.

---

## ADR-002: Postgres + pgvector as the single store

**Status:** Accepted (Phase 0)

**Context:** Retrieval needs vectors, document metadata (country, effective date, superseded_by) and filtering on that metadata.

**Decision:** Use PostgreSQL 16 with pgvector (HNSW index). It holds documents, chunks, metadata and embeddings. Metadata filters are plain SQL `WHERE` clauses. BM25 runs in-process with `bm25s` over the same chunks.

**Consequences:** One database to run and back up, and joins between vectors and metadata are free. Qdrant stays available as an ablation or scale option. At 1–3k chunks, pgvector performance is a non-issue.

---

## ADR-003: Self-hosted Langfuse v3 for observability

**Status:** Accepted (Phase 0)

**Context:** Every request needs tracing: detected variety, query versions, retrieval results, scores, tokens, cost and latency. The data shouldn't have to leave the machine during development.

**Decision:** Run Langfuse v3 in Docker Compose: web, worker, its own Postgres, ClickHouse, Redis and MinIO. It gets a separate Postgres from the app DB, so Langfuse migrations never touch application data. Headless init (`LANGFUSE_INIT_*`) creates the project and API keys on first start, so `docker compose up` gives a working tracing endpoint with no clicking.

**Consequences:** The full stack needs roughly 4 GB of RAM. All ports bind to `127.0.0.1`. The default secrets are for development only and must be overridden in any deployment. Deployment may switch to Langfuse Cloud. That choice will be recorded as a new ADR.

---

## ADR-004: No LLM framework at the core

**Status:** Accepted (Phase 0)

**Context:** This project is evaluated in interviews, and every pipeline step must be explainable and individually ablatable.

**Decision:** Build the pipeline by hand: normalization, translation, retrieval, fusion, reranking and generation. Reimplementing one configuration in LlamaIndex or LangChain later is optional.

**Consequences:** More code to write, but full control over each ablation variable and no hidden prompts.
