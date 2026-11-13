# Annotation guide: Musaid evaluation queries

This guide is for anyone who writes or labels queries for the Musaid benchmark. That includes the second annotator, who labels 50 queries on their own for the agreement check. Read it in full before writing your first query. When a query doesn't fit a rule, ask; don't guess. Every new ruling gets added to the [Rulings log](#rulings-log) at the end so the next person applies it the same way.

**The benchmark in one paragraph.** The knowledge base (KB) is 354 English help articles for a fictional e-wallet, Sahla Pay, operating in Saudi Arabia (SA), the UAE (AE) and Egypt (EG). It is split into 600 chunks. Customers ask in English or in one of five Arabic varieties. For each query we record which chunks answer it (the *gold chunks*), a short English reference answer, and the facts any correct answer must contain. Retrieval systems are then scored on whether they find the gold chunks.

---

## 1. Where things live

| What | Where |
|---|---|
| Chunks you label against | `data/kb/chunks.jsonl` (frozen; see ADR-009) |
| Articles, readable | `data/kb/articles/` |
| Query sources you write | `data/eval/source/*.yaml` |
| Built query file | `data/eval/queries.jsonl` (generated; never edit by hand) |
| Dev and test splits | `data/eval/dev.jsonl`, `data/eval/test.jsonl` |
| Test lock | `data/eval/test.lock.json` |

**Tools**

```
python -m musaid.benchmark.search "dispute deadline card payment"   # find candidate chunks
python -m musaid.benchmark.search "transfer limit" --country SA     # only chunks covering SA
python -m musaid.benchmark.search --show kb-0077#c0                 # read a chunk in full
python -m musaid.benchmark.build                                    # validate, rebuild, update stats
python -m musaid.benchmark.build --final                            # before locking: warnings fail too
```

The search is plain BM25 over the English chunks. It finds candidates only, so try two or three wordings. It is separate from the retrieval code being evaluated. Progress against every target is in `docs/EVAL_STATS.md`.

The KB is frozen. If you find an error in an article while labeling, write it in the Rulings log; don't fix the article. Changing a chunk would silently change the meaning of labels that point at it.

---

## 2. How to write a query

Write as a real customer would, not as a test designer.

1. **Start from an intent, not from a chunk.** Picture a person with a problem: "I sent 500 riyals to the wrong number." Write their message. Only then search the KB for the answer.
2. **Don't copy KB wording.** Customers don't say "pre-authorization" or "dispute deadline". English queries especially must not reuse the article title or its distinctive phrases. Copied wording makes lexical search look better than it is.
3. **Don't write from the glossary.** Keep `data/glossary/` closed while you write. Glossary-assisted translation is one of the ablations (#8). If the queries are built from glossary forms, that ablation is graded on its own answer key.
4. **Write each Arabic variety natively.** Don't translate an English query word for word. A Gulf customer says "ابي ارجع فلوسي"; they don't say "أريد استرداد أموالي".
5. **Keep realistic noise.** Typos, missing hamzas, no punctuation, run-on sentences and a bit of context ("I'm traveling tomorrow") are all fine. Don't add noise for its own sake, and keep the query understandable to a human agent.
6. **One question per query.** "How do I freeze my card and also what's the ATM fee?" is two queries. A multi-hop query (§6) is one question whose answer happens to span two chunks.
7. **Length.** Most queries are 5–30 words. A few longer ones (up to about 60 words) are good, because real customers explain.

---

## 3. Language varieties

Every query gets exactly one `variety`. Label the variety the query is written in, not where the customer lives.

| `variety` | Definition | Markers (examples, not a checklist) |
|---|---|---|
| `english` | English only. Arabic place or product names in Latin letters are fine ("Riyadh", "Nafath"). | — |
| `msa` | Modern Standard Arabic, the register of formal writing. No dialect words. | أريد، كيف يمكنني، هل، لماذا، لم أستلم |
| `gulf` | Saudi, Emirati or other Gulf dialect in Arabic script. | ابي/أبغى، وش، ليش، حق، للحين، مو، سويت |
| `levantine_egyptian` | Levantine or Egyptian dialect in Arabic script. | عايز، ازاي، ليه، بتاع، لسه، مش / بدي، شو، كيف، هلق، تبع |
| `code_switched` | Arabic script (any register) with at least one English word **in Latin letters** that a speaker would naturally switch to. | "الـ card حقي blocked"، "ابي اسوي transfer" |
| `arabizi` | Arabic written in Latin letters, usually with digit letters (2, 3, 5, 7…). English words mixed in are still Arabizi. | "kif arja3 floosi", "el card mesh shaghal" |

**Edge cases**
- English loanwords written in Arabic script ("الكرت"، "الأبلكيشن") don't make a query code-switched. The English has to be in Latin letters.
- A dialect query with one MSA phrase is still dialect. An MSA query with one dialect word is dialect: label by the most dialectal word.
- Arabizi that is really English with one Arabic word ("my 7awala failed") counts as Arabizi only if most content words are Arabic. Otherwise it is English.
- `script` is derived by the builder (`arabic`, `latin` or `mixed`), so you don't set it.

**Dialect is not a country.** A Gulf-dialect query doesn't mean the customer is in SA or AE: Egyptians and Syrians live in Riyadh, and Saudis live in Dubai. Never infer `country` from dialect alone (§7).

---

## 4. Query types

Pick the **one** type that best describes what makes the query hard. When two apply, the higher row wins.

| `type` | Use when | Example intent |
|---|---|---|
| `unanswerable` | The KB doesn't answer it (§8). | "Do you offer personal loans?" |
| `ambiguous` | The answer depends on a country the query doesn't give (§7). | "What's the fee for sending money abroad?" |
| `superseded_trap` | An old edition of the policy matches the query well, and only the current one is correct. | "Transfer limit in Saudi", where kb-0035 (2025) competes with kb-0034 |
| `multi_hop` | A full answer needs facts from 2–3 different chunks. | "Can I raise my limit before verifying, and what's the limit now?" |
| `number_sensitive` | The answer hinges on a fee, limit, percentage, deadline or day count. | "How many days do I have to dispute a card payment?" |
| `country_specific` | The answer is a rule (not a number) that differs by country, and the country is given or implied. | "What documents do I need in Egypt?" |
| `troubleshooting` | Something is broken and the customer wants it fixed. | "The app keeps closing when I open it" |
| `procedural` | How to do something, step by step. | "How do I add my card to Apple Pay?" |
| `policy_eligibility` | Whether something is allowed or who qualifies. | "Can my 15-year-old have an account?" |
| `factual` | A plain fact that fits nothing above. | "What does 'In review' mean?" |

---

## 5. Gold chunks

Gold chunks are the chunks a good retriever must return for the query to be answerable from the KB.

**Rules**
1. **1–3 gold chunks per answerable query.** Pick the *smallest set* that fully answers the question. If one chunk answers it fully, that is the only gold chunk.
2. **A gold chunk must contain the answer, not point to it.** A FAQ line saying "See Dispute deadlines" isn't gold; the chunk with the deadline is.
3. **Equivalent chunks.** If two chunks *each* fully answer the query on their own (near-duplicates such as kb-0071 "Refund timelines" and kb-0072 "When will I get my money back?"), list both. Order doesn't matter; relevance is binary.
4. **Partial chunks aren't gold.** A chunk that covers the topic but not the asked fact is a hard negative, not gold.
5. **Never gold: superseded chunks.** A chunk whose article has `superseded_by` set is never gold for a question about current policy. The one exception is a query that explicitly asks about the old policy ("what was the limit last year?"). Allow at most five of those in the whole set.
6. **Country.** If the query gives a country, the gold chunk must cover that country. Check the chunk's `countries` and its headings.
7. **Read every gold chunk in full** before you label it. Use the search helper to *find* candidates, never to *decide*. Then set `verified: true`. The builder rejects unverified answerable queries from the final set.
8. **Check for competitors.** Before you finalize, search once more with different words. If another chunk also fully answers the query, rule 3 applies.

**Gold source (ADR-010).** About 70% of answerable queries should have their gold answer in one of the 40 hand-rewritten articles (50 chunks); about 30% should point at draft articles. You don't enter this; the builder derives `gold_source` from the first gold chunk (`rewritten`, `draft` or `mixed` for multi-hop across both). Keep an eye on the running count the builder prints.

**Don't overload one chunk.** No chunk should be gold for more than 8 distinct intents. A parallel group counts as one intent. Spread queries across the rewritten articles; don't write 20 queries on refund timelines.

---

## 6. Multi-hop queries

- The answer needs **2 or 3** chunks, and each one contributes a fact the answer can't do without. A second chunk that merely repeats context isn't a hop.
- Hops can sit in one article (two chunks of kb-0028 "Account tiers and balance limits") or across articles (limit increase + current limit).
- `critical_facts` must include at least one fact from each gold chunk.

---

## 7. Ambiguous queries and country

**A query is ambiguous** (`type: ambiguous`, `needs_clarification: true`) when all of these hold:
1. The KB gives a different answer for different countries, **and**
2. the query neither states nor implies a country, **and**
3. a support agent could not answer correctly without asking.

If the answer is the same in all three countries, the query isn't ambiguous, even with no country given.

**What implies a country** (then set `country` and treat the query as unambiguous):

| Signal | Country |
|---|---|
| Currency: SAR, riyal, ريال (SA), AED, dirham, درهم (AE), EGP, pound, جنيه (EG) | as listed |
| City or region: Riyadh, Jeddah, Dubai, Abu Dhabi, Cairo, Alexandria | as listed |
| Country-only services or IDs: Iqama, Nafath, SADAD (SA); Emirates ID, UAE Pass (AE); InstaPay, الرقم القومي (EG). A plain "national ID" doesn't count: Saudi Arabia has one too. | as listed |
| An explicit "in Saudi", "في الإمارات", "fi masr" | as listed |

Dialect alone **doesn't** imply a country (§3). "ريال" alone is SA for this KB, because the other two currencies are dirham and pound.

**Labeling an ambiguous query:** `country: null`, `answerable: true`, `needs_clarification: true`. Gold chunks are the chunks that hold the per-country answers (often one fee table or limits chunk that covers all three). `reference_answer` gives the answer per country in one or two sentences. `critical_facts` may be empty: the scored behavior is asking which country, not quoting a number.

Aim for about 8% of all queries (~36). Ambiguous queries don't count toward the 70/30 gold split.

---

## 8. Unanswerable queries

A query is unanswerable when **the KB has no chunk that answers it**. Set `answerable: false`, `gold_chunk_ids: []` and give `unanswerable_reason`:

| `unanswerable_reason` | Meaning | Share of unanswerables |
|---|---|---|
| `not_in_kb` | A plausible Sahla Pay question the KB doesn't cover: crypto, loans, an unlisted country, a feature that doesn't exist. | at least 60% |
| `account_specific` | Needs the customer's own data or an action: "why is my transfer #4821 stuck?", "refund me now". | about 25% |
| `out_of_domain` | Not about Sahla Pay at all. | at most 15% |

**Search before you label.** Run at least three searches with different wording. If the KB *explicitly* says Sahla Pay doesn't offer something (the wallet balance "does not earn interest or profit"), then "do I earn interest on my balance?" is **answerable** and that chunk is gold. "Not in the KB" means the KB is silent.

Near-misses are the valuable ones: a question that *looks* covered but isn't (for example, a transfer corridor to a country the KB doesn't list). Aim for 10–15% of all queries (~55).

---

## 9. Reference answer and critical facts

**`reference_answer`**: one or two English sentences that a correct answer must agree with. Use only facts from the gold chunks, and don't add advice the KB doesn't give.

**`critical_facts`**: the short strings the automatic fidelity check looks for in a generated answer, in any language.
- 0–4 items, each **atomic**: one number with its unit, one deadline, one named condition. Use `"SAR 20"`, not `"a fee of SAR 20 applies"`.
- Copy numbers **exactly as the gold chunk displays them**, including currency code, commas and unit: `"AED 5,000"`, `"60 days"`, `"3 business days"`. The builder checks that every critical fact appears in a gold chunk body.
- Include the condition when the answer depends on it: `"after the dispute is approved"`.
- Procedural and troubleshooting queries may have no numbers. Then list the one or two steps that must not be missed (`"Freeze card"`), or leave the list empty.
- Leave `critical_facts` empty for unanswerable queries.

---

## 10. The parallel subset

Forty intents are written in **all six varieties**: 240 queries that let us compare varieties on the same question.

- Give all six queries the same `parallel_group` (`pg-001` to `pg-040`), the same gold chunks, `country`, `type`, `reference_answer` and `critical_facts`.
- Write each variety natively (§2 rule 4). The six queries should carry the same intent, not be translations of each other.
- If the intent implies a country, every version must imply it. Don't let the English version say "in Dubai" while the Gulf version says nothing.
- Spread the 40 intents across types and categories. Most of them should point at the rewritten articles (ADR-010). Include a few superseded traps and a few number-sensitive intents. Leave out ambiguous and unanswerable intents: the parallel subset compares retrieval quality on identical answers.

The remaining ~220 queries follow this variety mix: English 30%, MSA 20%, Gulf 18%, Levantine/Egyptian 12%, code-switched 12%, Arabizi 8%.

---

## 11. Difficulty

A rough, honest guess at how hard the query is for a retriever. It isn't used for scoring; it's used to read results.

| `difficulty` | Meaning |
|---|---|
| `easy` | The query shares obvious words with the gold chunk (after translation), and there's no competing chunk. |
| `medium` | Paraphrased, or there's one plausible competing chunk. |
| `hard` | Slang, heavy noise, a buried exception, a superseded trap, or multi-hop. |

---

## 12. The record

You write YAML in `data/eval/source/`. The builder adds `script`, `gold_source` and `split`, and checks everything.

```yaml
- qid: q-0231
  query: "ابي ارجع فلوسي من تحويل غلط، كم ياخذ وقت؟"
  variety: gulf
  type: number_sensitive
  country: SA
  answerable: true
  needs_clarification: false
  gold_chunk_ids: [kb-0075#c1]
  reference_answer: "..."
  critical_facts: ["..."]
  parallel_group: null
  difficulty: medium
  verified: true
  notes: ""
```

- `qid` is permanent. Never reuse or renumber one, even after deleting a query.
- `country` is `SA`, `AE`, `EG` or `null`.
- `unanswerable_reason` is required when `answerable: false` and forbidden otherwise.
- `notes` is free text: why a label was hard, which competitor chunk was considered.

---

## 13. Dev/test split and lock

- **Test: 275 queries. Dev: everything else (at least 175).** Never tune anything on test.
- The split is stratified by variety and type, using a fixed seed.
- **A parallel group goes entirely to one split.** So do queries written as near-paraphrases of each other.
- Tie near-paraphrases with `split_with: q-NNNN` in the source; the split keeps tied queries together.
- `python -m musaid.benchmark.split assign` writes `data/eval/split.json`. It's append-only: existing queries never change sides. ADR-012 has the method.
- After every query is verified, `python -m musaid.benchmark.split lock` records the test file's SHA-256 in `data/eval/test.lock.json`, together with the `body_sha1` of every gold chunk. CI fails if either changes. To fix a test label after locking, write an ADR and re-lock; never edit quietly.

---

## 14. Second-annotator check

A second Arabic speaker labels **50 queries** on their own:

- The sample is stratified: at least 35 Arabic-variety queries, about 6 ambiguous and about 6 unanswerable.
- They see only the query text and this guide. They don't see the first annotator's labels or notes.
- They set `answerable`, `needs_clarification`, `variety`, `type` and the gold chunks, using the same search helper.

**What we report**
- **Gold chunks:** the share of queries where the two gold sets overlap at all, the share with exactly the same set, and mean Jaccard.
- **Answerable, needs-clarification, variety and type:** Cohen's κ for each.

Disagreements are settled by discussion. The outcome goes in the Rulings log, and the agreed label replaces both. The agreement numbers are reported *before* adjudication.

---

## Rulings log

Add one line per decision that the rules above didn't settle: date, query id, ruling.

- 2026-11-12, pg-003 and pg-009: **when more than 3 chunks each fully answer a query**, keep 3 in this order: the help article that owns the topic, then the legal document, then a FAQ, then an announcement or release note. Name the chunks you left out in `notes`, so a retriever that returns them isn't misread as wrong when reading failures.
- 2026-11-12, pg-004: **a procedure that is the same in every country isn't ambiguous**, even when a number in the same chunk differs by country (delivery times), as long as the question asks for the steps and not the number.
- 2026-11-14, q-0021 and q-0040: **words borrowed across dialects are realistic; keep them.** Gulf speakers often say أي حاجة, and لألوه is Levantine for "for himself" (as in إلو / حقه). Label by the dialect of the query as a whole (§3), and don't "correct" a borrowed word into a textbook form. The native annotator's judgment on what people actually say wins.
