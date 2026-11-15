# Retrieval results

**Dev split only.** The test set isn't locked yet (ADR-012), so no number here comes from test. Dev labels are still being verified and can shift slightly. Raw runs: `eval/results/<config>__dev.json`.

Query varieties are English, MSA, Gulf, Egyptian and code-switched (ADR-013). Scored queries: 146 dev queries with gold chunks (answerable plus ambiguous). Metric is recall@10 unless stated. CPU latencies are from one laptop and vary by about ±40% between runs; compare them in orders of magnitude, not decimals.

## Phase 3 baselines (dev)

| | A: BM25, raw query | B: dense bge-m3, raw query |
|---|---|---|
| **Overall recall@10** | 0.243 | **0.789** |
| MRR@10 | 0.228 | 0.721 |
| nDCG@10 | 0.204 | 0.674 |
| Query latency (CPU) | 0.1 ms | 176 ms |

### By variety (recall@10)

| Variety | n | A: BM25 | B: bge-m3 |
|---|---|---|---|
| English | 38 | 0.553 | 0.886 |
| MSA | 32 | 0.031 | 0.786 |
| Gulf | 30 | 0.000 | 0.672 |
| Egyptian | 23 | 0.000 | 0.710 |
| Code-switched | 23 | 0.587 | 0.862 |

Parallel subset only (same 16 intents in each variety, the fair comparison): bge-m3 scores MSA 0.865, code-switched 0.865, English 0.792, Egyptian 0.646, Gulf 0.521.

### By query type (recall@10)

| Type | n | A: BM25 | B: bge-m3 |
|---|---|---|---|
| procedural | 12 | 0.167 | 1.000 |
| ambiguous | 13 | 0.231 | 0.923 |
| troubleshooting | 22 | 0.364 | 0.909 |
| factual | 11 | 0.227 | 0.818 |
| country_specific | 8 | 0.208 | 0.812 |
| policy_eligibility | 13 | 0.256 | 0.744 |
| number_sensitive | 56 | 0.238 | 0.694 |
| **superseded_trap** | 10 | 0.167 | **0.667** |
| multi_hop | 1 | 0.000 | 0.500 |

Gold source: bge-m3 0.779 on rewritten gold, 0.811 on draft gold (ADR-007 comparison).

## What the baselines say

- **Weakest variety: Gulf.** On the parallel subset bge-m3 reaches 0.52 on Gulf and 0.65 on Egyptian, against 0.87 for MSA. Dialect costs a quarter to a third of recall for the same intent.
- **Code-switched queries do as well as MSA** (0.87). The English words in them ("transfer", "dispute", "card") land close to the English chunks.
- **Weakest types: number-sensitive (0.69) and superseded traps (0.67).** Old editions look just as relevant to an embedding model; ablation #9 (effective-date metadata) targets this.
- **BM25 on the raw query is the floor the spec predicts:** zero for Gulf and Egyptian and 0.03 for MSA, because nothing in Arabic matches an English index. It only works on English and on the English words inside code-switched queries.
- Multi-hop has one dev query, so its number means nothing on dev (ADR-012).

## Phase 4 ablations (dev)

One variable changes per row. Recall@10 unless stated; latency is query-time CPU encoding and search.

| # | Configuration | Overall | English | MSA | Gulf | Egyptian | Code-sw. | ms/query |
|---|---|---|---|---|---|---|---|---|
| 1 | BM25, raw query | 0.243 | 0.553 | 0.031 | 0.000 | 0.000 | 0.587 | 0.1 |
| 2 | Dense bge-m3, raw query | **0.789** | **0.886** | **0.786** | **0.672** | **0.710** | **0.862** | 176 |
| 3 | Dense multilingual-e5-large, raw query | 0.717 | 0.829 | 0.771 | 0.633 | 0.573 | 0.710 | 157 |

### #3: a second multilingual embedding model

`intfloat/multilingual-e5-large` (560M parameters, the same size class as bge-m3), with its trained `query: ` / `passage: ` prefixes and the same 512-token limit. Config `dense_e5_large_raw`.

- **The model choice matters, and bge-m3 wins.** e5-large loses 0.07 recall@10 overall (paired randomization test on dev, p ≈ 0.003; 36 of 146 queries change). MRR@10 is 0.686 against 0.721.
- **It doesn't lose evenly across varieties.** The biggest drops are code-switched (−0.15) and Egyptian (−0.14). MSA barely moves (−0.02). On the parallel subset, e5 is level on Gulf (0.542 against 0.521, inside noise) and loses 0.20 on Egyptian. So the two models disagree most on dialect and code-switching, not on MSA.
- **Superseded traps get worse** (0.53 against 0.67), so e5 separates old and current editions even less well than bge-m3.
- **Cost is a wash:** query latency is about the same on CPU, and both store one 1,024-dimensional vector per chunk.
- **Decision:** bge-m3 stays the dense model for the remaining ablations (#5 onwards), as the spec planned.
