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

---

## ADR-005: KB authored as Markdown with fact placeholders

**Status:** Accepted (Phase 1)

**Context:** The KB needs the same value (a fee, a deadline) repeated across near-duplicate articles, fee schedules and country sections. A typo in one copy creates an accidental contradiction, and that silently corrupts the benchmark's gold answers (spec §10).

**Decision:**
- Articles are Markdown files with YAML front matter in `data/kb/articles/`, which are easy to rewrite by hand and review in diffs.
- Every governed value is a `{{fact_id}}` placeholder resolved from `data/kb/facts.csv` at build time.
- A literal amount or percentage in an article is a build error.
- Each fact has an effective date. Superseded values keep their own dated IDs, so archived articles render their old values.
- `python -m musaid.ingest.build` validates the KB and renders `kb.jsonl`, `chunks.jsonl` and `docs/KB_STATS.md`. CI fails if any of these are stale.

**Consequences:** Contradictions become impossible by construction, except where intended (archived articles). `facts.csv` doubles as the answer key for `critical_facts` and for the Phase 5 fidelity checker. The cost: authors write `{{fees.card_replacement.SA}}` instead of `SAR 25`, and worked examples with computed amounts are not allowed.

---

## ADR-006: Structure-aware chunking with country-tagged sections

**Status:** Accepted (Phase 1)

**Context:** Gold labels in the benchmark point at chunk IDs. Chunk boundaries therefore decide what counts as a correct retrieval, and must never cut a fee table or a procedure in half.

**Decision:**
- Split on `##`/`###` headings, then pack adjacent sections greedily: up to 400 tokens, stopping once a chunk reaches 200. Short trailing sections join the previous chunk.
- Tables and lists are atomic, together with a lead-in line ending in `:`.
- A heading that names a country (`## Egypt`) tags its chunk with that country. Sections for different countries are never packed together.
- Each chunk's `text` gets a prefix of title, section path and countries. The `body` without the prefix is what users see as the citation.
- Tokens are approximated as words plus punctuation, which is close enough for sizing.

**Consequences:** Country sections become separately retrievable and filterable, which ablation #10 needs. Chunk IDs (`kb-0071#c2`) are deterministic, and `body_sha1` detects when a chunk's content changes under an existing gold label. **The chunker must be frozen (`CHUNKER_VERSION`) before Phase 2 labeling starts.** Any later change requires re-checking labels whose `body_sha1` moved.

---

## ADR-007: Hand-rewrite 40 of the 200 articles, not all of them

**Status:** Accepted (Phase 1)

**Context:** The spec (Phase 1 step 3) calls for rewriting every LLM-drafted article by hand and injecting the mandatory mess, so the KB doesn't read as uniformly clean LLM text, which would inflate retrieval scores (spec §10). With 200 drafted articles and a 10–15 hours/week budget alongside a full-time job, a full rewrite would consume most of the remaining Phase 1 time and delay the benchmark (Phase 2), which is the project's centerpiece.

**Decision:**
- Rewrite and inject mess into **40 articles** (20%), marked `rewrite_target = yes` in `data/kb/inventory.csv`. The other 160 stay as LLM drafts (`status: draft`).
- The 40 are split across categories in the same proportions as the KB: account 6, transfers 8, refunds 6, cards 6, fees 4, security 4, troubleshooting 4, legal 2.
- Selection favours the articles the benchmark leans on hardest:
  - all four superseded pairs (kb-0034/0035, kb-0037/0038, kb-0071/0073, kb-0131/0134)
  - the main near-duplicate groups (kb-0007/0009, kb-0071/0072, kb-0010/0028/0140)
  - the strongest country-specific and buried-exception articles in each category
- `docs/KB_STATS.md` tracks progress against the 40 targets.

**Consequences:**
- 80% of the KB is unedited LLM text. This is a known limitation, and it's disclosed in the dataset card and the README's limitations section.
- The limitation is also measured. Since every article's rewrite status is known, the Phase 3–4 eval harness reports retrieval metrics separately for queries whose gold article is rewritten and queries whose gold article is a draft. A large gap means the drafts make retrieval artificially easy, and that becomes a reported finding rather than a hidden bias.
- The real-world sanity check (spec §5.6) carries more weight. It is the main evidence that results hold outside the KB we wrote.
- Gold labels must be checked against rendered text, which `body_sha1` already supports. A rewrite after labeling changes chunk hashes, so **rewrites of the 40 should be finished before Phase 2 labeling starts.**

---

## ADR-008: Grow the KB to about 1,000–1,200 chunks

**Status:** Accepted (Phase 1)

**Context:** The 200 help articles produce 222 chunks (about 50,000 tokens), against the spec's 1,000–3,000. Real help-center articles are short, so this is realistic per article, but the corpus as a whole is too small. With few candidates per query, retrieval is artificially easy and scores would be inflated (spec §10). Chunk size is already within the spec's 200–400 tokens (ADR-006), so growth has to come from more text, not smaller chunks: roughly 220,000–250,000 tokens in total.

**Decision:** Grow the KB in three stages. Each stage leaves a complete, usable KB.

| Stage | Content | Est. chunks |
|---|---|---|
| 1 | Long-form legal documents (`article_type: legal_document`, kb-0201..kb-0216): full Terms of Use, Card Terms, Privacy Notice, full Fees and Charges Schedule, dispute, AML, complaints and other policies, plus **archived 2025 editions** of the Terms, Card Terms and fee schedule | ~250 |
| 2 | Remittance corridor guides (e.g. Saudi Arabia/UAE to India, Pakistan, the Philippines, Egypt) and card-abroad travel guides | ~300 |
| 3 | Realistic noise: release notes, promotions (expired and current), service notices, money tips, glossary | ~300 |

- **Same rules as the rest of the KB:** governed values come from `facts.csv`, and validation is unchanged.
- **Archived editions are near-identical to the current ones.** They differ only in clauses whose facts changed, which makes them the hardest superseded-policy negatives in the benchmark.
- **Category shares in `KB_STATS.md` count help articles only.** Legal documents are listed separately, so the spec's category split still describes the help center.
- **Stop at about 1,000–1,200 chunks.** Beyond that, each extra chunk adds little retrieval difficulty for the authoring and review cost.

**Consequences:**
- The new text is LLM-drafted. It's outside the ADR-007 rewrite targets and disclosed the same way.
- Adding documents doesn't change existing chunk IDs, but it can create a second valid answer for a query. **Growth should finish before Phase 2 labeling**, so gold labels are complete.
- Legal documents let Phase 2 include hard queries whose only answer sits in a dense clause, for example governing language or liability caps.

### ADR-008 revision (Phase 1): stop at about 650–750 chunks

**Context:** Stage 1 added 95 chunks, not the ~250 estimated: the 16 legal documents came out at 3–21 chunks each. Reaching 1,000 chunks would need roughly 165,000–210,000 more tokens of drafted text, about seven times Stage 1, for diminishing gains in retrieval difficulty.

**Revised decision:** Stop growth at about **650–750 chunks**:

| Stage | Content | Est. chunks |
|---|---|---|
| 1 (done) | 16 legal documents, incl. archived editions | 95 (KB: 317) |
| 2 | Remittance corridor guides, card-abroad travel guides, life-event guides (`article_type: guide`) | ~230 |
| 3 | Small noise set: release notes, promotions, service notices | ~100 |

**Revised consequences:**
- The KB is below the spec's 1,000-chunk minimum. This is stated in the README's known limitations and in the dataset card, with the chunk count.
- The evidence that retrieval isn't artificially easy comes from three places: the rewritten-vs-draft comparison (ADR-007), the hard negatives (archived editions, near-duplicates, templated corridor guides), and the real-world sanity check (spec §5.6).
- Growth can resume later without breaking existing gold labels, because new documents only add chunks. Doing so would require re-checking gold completeness for affected queries.
