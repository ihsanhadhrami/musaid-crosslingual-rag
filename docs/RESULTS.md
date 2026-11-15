# Retrieval results

**Dev split only.** The test set isn't locked yet (ADR-012), so no number here comes from test. Dev labels are still being verified and can shift slightly. Raw runs: `eval/results/<config>__dev.json`.

Scored queries: 165 dev queries with gold chunks (answerable plus ambiguous). Metric is recall@10 unless stated.

## Phase 3 baselines (dev)

| | A: BM25, raw query | B: dense bge-m3, raw query |
|---|---|---|
| **Overall recall@10** | 0.241 | **0.716** |
| MRR@10 | 0.216 | 0.653 |
| nDCG@10 | 0.198 | 0.610 |
| Query latency (CPU) | 0.08 ms | 124 ms |

### By variety (recall@10)

| Variety | n | A: BM25 | B: bge-m3 |
|---|---|---|---|
| English | 38 | 0.553 | 0.886 |
| MSA | 32 | 0.031 | 0.786 |
| Gulf | 30 | 0.000 | 0.672 |
| Levantine/Egyptian | 23 | 0.000 | 0.710 |
| Code-switched | 23 | 0.587 | 0.862 |
| **Arabizi** | 19 | 0.228 | **0.158** |

Parallel subset only (same 16 intents in each variety, the fair comparison): bge-m3 scores MSA 0.865, code-switched 0.865, English 0.792, Levantine/Egyptian 0.646, Gulf 0.521, Arabizi 0.062.

### By query type (recall@10)

| Type | n | A: BM25 | B: bge-m3 |
|---|---|---|---|
| procedural | 13 | 0.154 | 0.923 |
| ambiguous | 14 | 0.286 | 0.929 |
| troubleshooting | 26 | 0.385 | 0.808 |
| factual | 12 | 0.208 | 0.750 |
| country_specific | 9 | 0.185 | 0.722 |
| policy_eligibility | 14 | 0.238 | 0.691 |
| number_sensitive | 64 | 0.224 | 0.617 |
| **superseded_trap** | 12 | 0.167 | **0.583** |
| multi_hop | 1 | 0.000 | 0.500 |

Gold source: bge-m3 0.687 on rewritten gold, 0.786 on draft gold (ADR-007 comparison).

## What the baselines say

- **Weakest variety: Arabizi.** Dense retrieval handles Arabic script well, but Arabizi drops to 0.16, *below* plain BM25 (0.23). BM25 at least matches the English words Arabizi speakers mix in ("limit", "pin", "atm"); bge-m3 doesn't map Latin-script Arabic to its meaning. This is the gap ablation #9 (Arabizi transliteration) targets.
- **Among Arabic-script varieties, Gulf is weakest** (0.52 on the parallel subset, against 0.87 for MSA). Dialect costs about a third of recall for the same intent.
- **Weakest type: superseded traps** (0.58), then number-sensitive queries (0.62). Old editions look just as relevant to an embedding model; ablation #10 (effective-date metadata) targets this.
- **BM25 on the raw query is the floor the spec predicts:** near zero for every Arabic-script variety, because nothing in Arabic matches an English index.
- Multi-hop has one dev query, so its number means nothing on dev (ADR-012).

## Phase 4 ablations (dev)

One variable changes per row. Recall@10 unless stated; latency is query-time CPU encoding and search.

| # | Configuration | Overall | English | MSA | Gulf | Lev/Egy | Code-sw. | Arabizi | ms/query |
|---|---|---|---|---|---|---|---|---|---|
| 1 | BM25, raw query | 0.241 | 0.553 | 0.031 | 0.000 | 0.000 | 0.587 | 0.228 | 0.08 |
| 2 | Dense bge-m3, raw query | **0.716** | **0.886** | **0.786** | **0.672** | **0.710** | **0.862** | **0.158** | 124 |
| 3 | Dense multilingual-e5-large, raw query | 0.646 | 0.829 | 0.771 | 0.633 | 0.573 | 0.710 | 0.105 | 115 |

### #3: a second multilingual embedding model

`intfloat/multilingual-e5-large` (560M parameters, the same size class as bge-m3), with its trained `query: ` / `passage: ` prefixes and the same 512-token limit. Config `dense_e5_large_raw`.

- **The model choice matters, and bge-m3 wins.** e5-large loses 0.07 recall@10 overall (paired randomization test on dev, p ≈ 0.003; 41 of 165 queries change). MRR@10 is 0.617 against 0.653.
- **It doesn't lose evenly across dialects.** The biggest drops are in code-switched (−0.15) and Levantine/Egyptian (−0.14). MSA barely moves (−0.02). On the parallel subset, e5 is level on Gulf (0.542 against 0.521, inside noise) and loses 0.20 on Levantine/Egyptian. So the two models disagree most on dialect, not on MSA.
- **Neither model reads Arabizi.** Both score 0.062 on the parallel Arabizi queries. Changing the embedding model doesn't touch the worst gap; it needs the transliteration step (#9).
- **Superseded traps get worse** (0.44 against 0.58), so e5 separates old and current editions even less well than bge-m3.
- **Cost is a wash:** query latency is about the same (115 against 124 ms on CPU), and both store one 1,024-dimensional vector per chunk.
- **Decision:** bge-m3 stays the dense model for the remaining ablations (#5 onwards), as the spec planned.
