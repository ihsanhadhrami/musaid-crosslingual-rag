# KB Style Guide: Sahla Pay Help Center

Sahla Pay is fictional. Every article is original writing for this project: no text is copied or paraphrased from a real help center, and nothing comes from any employer (spec §5.1).

## 1. Where things live

| File | Purpose |
|---|---|
| `data/kb/facts.csv` | **The single source of truth** for every fee, limit, deadline, age, document and support hour |
| `data/kb/inventory.csv` | The plan: all 200 articles with category, type, countries and intended mess |
| `data/kb/articles/kb-NNNN-slug.md` | One source article: YAML front matter followed by a Markdown body |
| `data/kb/kb.jsonl`, `chunks.jsonl` | **Generated.** Never edit by hand |
| `docs/KB_STATS.md` | **Generated.** Progress and coverage |

After any change, run `uv run python -m musaid.ingest.build`. CI runs `--check` and fails if the outputs are stale or the KB has errors.

## 2. Front matter

```yaml
---
doc_id: kb-0034
title: Daily and monthly transfer limits
category: transfers_payments        # see inventory.csv
section_path: [Transfers, Limits]
countries: [SA, AE, EG]             # or: all
effective_date: 2026-03-01
superseded_by: null                 # doc_id of the replacement, for archived articles
article_type: fee_table             # faq | procedure | fee_table | policy | troubleshooting
status: draft                       # draft -> rewritten once you've rewritten it by hand
mess: [country_specific, buried_exception]
---
```

## 3. Facts: never type a governed value

Any fee, percentage, limit, deadline, duration, age, ID document or support hour must be a placeholder:

```markdown
Sending money abroad costs {{fees.intl_transfer_pct.SA}} of the amount (minimum {{fees.intl_transfer_min.SA}}).
```

The build replaces each placeholder with the fact's `display` column. The rules:

- **Literal amounts and percentages (`SAR 20`, `1.5%`) are build errors.** Literal durations (`5 days`) are warnings. Use a fact unless the number truly isn't policy, for example "a 6-digit code".
- **Fact IDs follow `topic.COUNTRY`, with `ALL` for global facts.** Superseded values are `topic.COUNTRY@YYYY-MM-DD`, with `superseded_by` pointing at the replacement.
- **Changing a value means changing one row in `facts.csv`.** Every article picks it up. To change a policy over time, add a new row, mark the old row superseded, and keep the old article as an archived article (§6).
- **Articles may only use facts for their own `countries`.** A current article may not use a superseded fact.
- **No worked examples with computed numbers.** "Sending SAR 2,000 costs SAR 30" can't be checked against `facts.csv` and will drift.

## 4. Voice and formatting

- **Voice:** plain, direct, second person ("you"). Short sentences. No marketing ("seamless", "hassle-free", "rest assured"). Say what happens, then what to do.
- **Headings:** the body starts at `##` (the title comes from front matter). Use `###` for sub-sections. Country sections use the country name in the heading (`## Saudi Arabia`, `## UAE`, `## Egypt`). The chunker reads these headings and tags the chunk with that country.
- **Money:** currency code before the amount, thousands separators, no decimals unless needed: `SAR 1,000`, `AED 2.50`, `EGP 150`. This lives in the `display` column.
- **Durations:** always say whether days are **business days** or **calendar days**. Business days differ by country (see `calendar.business_days.*`).
- **Dates in text:** `1 March 2026`, never `01/03/2026`.
- **Procedures:** numbered steps, one action per step, using the app's words in **bold** ("Tap **Send** > **International**"). Put a lead-in line ending in `:` directly above the list, so the chunker keeps them together.
- **Fee tables:** one row per item. For multi-country tables, use one column per country. Put footnotes under the table as plain paragraphs, not inside cells.
- **Cross-references:** `[Visible title](kb-0042)`. The build renders the link as the title only and checks that the target exists.

## 5. Article types

| Type | Shape |
|---|---|
| `faq` | Short intro, then question-style `##` headings with 1–3 paragraph answers |
| `procedure` | One-line purpose, "Before you start" requirements, numbered steps, "What happens next" |
| `fee_table` | One sentence on scope, the table, footnotes, then exceptions in prose |
| `policy` | The rule, who it applies to, exceptions, consequences |
| `troubleshooting` | Symptom-led headings ("Card declined online"), likely causes, then fixes in order |

## 6. Mandatory realistic mess (spec §5.2)

Tag each article's `mess` honestly. `docs/KB_STATS.md` counts them.

- **`country_specific`:** the same topic with different values for SA, AE and EG. Prefer one article with per-country sections or table columns. Some topics also get country-only articles.
- **`buried_exception`:** the rule comes first and the exception comes two or three paragraphs later, in prose, with no heading announcing it. This should feel natural: real help centers bury exceptions because they were added later.
- **`near_duplicate`:** two articles answering the same need with different titles and framing ("Refund timelines" vs "When will I get my money back?"). The facts must agree, which placeholders guarantee. The wording must not be copy-pasted.
- **`superseded`:** an old article with an earlier `effective_date` and `superseded_by` set. It uses the `@date` facts. It reads like a normal article; it does not say it is outdated.
- **`cross_reference`:** "See also" links, or inline links to related articles.

## 7. The hand-rewrite pass (draft → rewritten)

LLM drafts are too clean and too uniform. Before setting `status: rewritten`:

1. **Vary the structure.** Not every article gets the same intro, headings and closing.
2. **Remove LLM tells:** "Here's everything you need to know", symmetrical bullet lists, an obligatory closing summary, "Please note that…" on every paragraph.
3. **Add texture a real support team would add.** Examples: a note added after a common complaint, a slightly awkward legacy sentence, a specific in-app button name, an exception that only makes sense with context.
4. **Check that every number is a placeholder,** and that the rendered text in `kb.jsonl` reads naturally ("from age 16", not "from age 16 years").
5. **Read it aloud as a customer.** Would they find the answer? If the answer is a buried exception, it should be findable but not easy.
