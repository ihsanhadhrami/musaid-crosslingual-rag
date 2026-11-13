"""Build data/eval/queries.jsonl from the hand-written YAML sources and check every rule
in docs/ANNOTATION.md that a machine can check.

uv run python -m musaid.benchmark.build            # validate, write queries.jsonl + EVAL_STATS.md
uv run python -m musaid.benchmark.build --check    # CI: fail on errors or stale outputs
uv run python -m musaid.benchmark.build --final    # also fail on unverified or incomplete work
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from musaid.benchmark.schema import (
    VARIETY_TARGET_SHARE,
    GoldSource,
    Query,
    QuerySource,
    QueryType,
    Script,
    Variety,
)
from musaid.benchmark.split import chunk_hashes, verify_lock
from musaid.ingest.articles import load_articles
from musaid.ingest.schema import ReviewStatus
from musaid.ingest.validate import Issue

ROOT = Path(__file__).resolve().parents[3]

MAX_INTENTS_PER_CHUNK = 8
MAX_OLD_POLICY_QUERIES = 5
PARALLEL_VARIETIES = set(Variety)

_ARABIC = re.compile(r"[ء-ي]")
_LATIN = re.compile(r"[A-Za-z]")

# Signals that imply a country (ANNOTATION.md §7). Dialect is deliberately absent.
_LATIN_SIGNALS = {
    "SA": r"sar|riyals?|riyadh|jeddah|dammam|mecca|makkah|iqama|e2ama|nafath|sadad|saudi|ksa",
    "AE": r"aed|dirhams?|dubai|abu dhabi|sharjah|emirates id|uae pass|uae|emarat",
    "EG": r"egp|pounds?|cairo|alexandria|instapay|egypt|masr|ma9r",
}
_ARABIC_SIGNALS = {
    "SA": r"ريال|الرياض|جدة|الدمام|مكة|إقامة|اقامة|نفاذ|سداد|السعودية",
    "AE": r"درهم|دراهم|دبي|أبوظبي|ابوظبي|الشارقة|الإمارات|الامارات",
    "EG": r"جنيه|القاهرة|الاسكندرية|الإسكندرية|انستاباي|إنستاباي|مصر|الرقم القومي",
}
# Arabic attaches prefixes (و ف ب ل ك ال) and suffixes, so \b isn't enough:
# "بالسعودية" and "مصرية" must match, "مصرح" (authorized) must not.
_AR_PREFIX = r"(?<![ء-ي])(?:[وف]?(?:[بلك]|ال|بال|لل|كال)?)"
_AR_SUFFIX = r"(?:ات|ي|ية)?(?![ء-ي])"
COUNTRY_SIGNALS: dict[str, re.Pattern[str]] = {
    c: re.compile(
        rf"\b(?:{_LATIN_SIGNALS[c]})\b|{_AR_PREFIX}(?:{_ARABIC_SIGNALS[c]}){_AR_SUFFIX}", re.I
    )
    for c in ("SA", "AE", "EG")
}


@dataclass(frozen=True)
class ChunkInfo:
    chunk_id: str
    doc_id: str
    title: str
    countries: tuple[str, ...]
    superseded: bool
    rewritten: bool
    has_old_edition: bool  # an older, superseded article points at this one
    body: str


@dataclass
class BenchResult:
    queries: list[Query] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]


def load_chunks(root: Path) -> dict[str, ChunkInfo]:
    articles = [s.meta for s in load_articles(root / "data" / "kb" / "articles")]
    rewritten = {m.doc_id for m in articles if m.status == ReviewStatus.REWRITTEN}
    newer = {m.superseded_by for m in articles if m.superseded_by}
    out = {}
    for line in (root / "data" / "kb" / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        out[c["chunk_id"]] = ChunkInfo(
            chunk_id=c["chunk_id"],
            doc_id=c["doc_id"],
            title=c["title"],
            countries=tuple(c["countries"]),
            superseded=c["superseded_by"] is not None,
            rewritten=c["doc_id"] in rewritten,
            has_old_edition=c["doc_id"] in newer,
            body=c["body"],
        )
    return out


def load_sources(src_dir: Path) -> tuple[list[tuple[str, dict]], list[Issue]]:
    raws, issues = [], []
    for path in sorted(src_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(data, list):
            issues.append(Issue("error", path.name, "file must hold a YAML list of queries"))
            continue
        for i, raw in enumerate(data):
            qid = raw.get("qid", f"#{i}") if isinstance(raw, dict) else f"#{i}"
            raws.append((f"{path.name}:{qid}", raw))
    return raws, issues


def script_of(text: str) -> Script:
    ar, la = bool(_ARABIC.search(text)), bool(_LATIN.search(text))
    if ar and la:
        return "mixed"
    return "arabic" if ar else "latin"


def norm(text: str) -> str:
    text = text.replace("’", "'").replace("**", "").replace(" ", " ").lower()
    return re.sub(r"\s+", " ", text)


def implied_countries(text: str) -> set[str]:
    return {c for c, pat in COUNTRY_SIGNALS.items() if pat.search(text)}


def gold_source_of(q: QuerySource, chunks: dict[str, ChunkInfo]) -> GoldSource | None:
    gold = [chunks[c] for c in q.gold_chunk_ids if c in chunks]
    if not q.answerable or not gold:
        return None
    kinds = {c.rewritten for c in gold}
    if q.type == QueryType.MULTI_HOP and len(kinds) == 2:
        return "mixed"
    return "rewritten" if gold[0].rewritten else "draft"


def check_queries(raws: list[tuple[str, dict]], chunks: dict[str, ChunkInfo]) -> BenchResult:
    res = BenchResult()

    def err(where: str, msg: str) -> None:
        res.issues.append(Issue("error", where, msg))

    def warn(where: str, msg: str) -> None:
        res.issues.append(Issue("warning", where, msg))

    sources: list[QuerySource] = []
    for where, raw in raws:
        try:
            sources.append(QuerySource.model_validate(raw))
        except ValidationError as e:
            for d in e.errors():
                err(where, f"{'.'.join(map(str, d['loc']))}: {d['msg']}")

    for qid, n in Counter(q.qid for q in sources).items():
        if n > 1:
            err(qid, f"qid used by {n} queries")
    for text, n in Counter(norm(q.query) for q in sources).items():
        if n > 1:
            err(text[:40], f"same query text appears {n} times")

    for q in sources:
        w = q.qid
        _check_one(q, chunks, lambda m, w=w: err(w, m), lambda m, w=w: warn(w, m))
        res.queries.append(
            Query(
                **q.model_dump(exclude={"verified", "notes", "split_with"}),
                script=script_of(q.query),
                gold_source=gold_source_of(q, chunks),
            )
        )

    old = [q.qid for q in sources if q.about_old_policy]
    if len(old) > MAX_OLD_POLICY_QUERIES:
        err("about_old_policy", f"{len(old)} queries ask about old policy; max is 5")

    _check_parallel(sources, err, warn)
    _check_chunk_load(sources, warn)
    res.queries.sort(key=lambda q: q.qid)
    return res


def _check_one(q: QuerySource, chunks: dict[str, ChunkInfo], err, warn) -> None:
    # Variety vs script (ANNOTATION.md §3).
    sc = script_of(q.query)
    if q.variety in (Variety.ENGLISH, Variety.ARABIZI) and sc != "latin":
        err(f"{q.variety} query must be Latin script only")
    if q.variety in (Variety.MSA, Variety.GULF, Variety.LEVANTINE_EGYPTIAN) and sc != "arabic":
        err(f"{q.variety} query has Latin letters; label it code_switched or remove them")
    if q.variety == Variety.CODE_SWITCHED and sc != "mixed":
        err("code_switched query needs Arabic script plus English in Latin letters")

    # Answerable / unanswerable / ambiguous consistency.
    if q.answerable:
        if q.type == QueryType.UNANSWERABLE:
            err("type unanswerable but answerable is true")
        if q.unanswerable_reason is not None:
            err("unanswerable_reason is set on an answerable query")
        if not q.gold_chunk_ids:
            err("answerable query has no gold chunks")
        if not q.reference_answer.strip():
            err("answerable query has no reference_answer")
        if not q.verified:
            warn("not verified: read every gold chunk, then set verified: true")
    else:
        if q.type != QueryType.UNANSWERABLE:
            err("answerable is false, so type must be unanswerable")
        if q.unanswerable_reason is None:
            err("unanswerable query needs unanswerable_reason")
        if q.gold_chunk_ids or q.critical_facts:
            err("unanswerable query must have no gold chunks or critical facts")
        if q.needs_clarification:
            err("unanswerable query can't also need clarification")

    if (q.type == QueryType.AMBIGUOUS) != q.needs_clarification:
        err("type ambiguous and needs_clarification must go together")
    if q.type == QueryType.AMBIGUOUS:
        if q.country is not None:
            err("ambiguous query must have country: null")
        if q.parallel_group:
            err("ambiguous queries stay out of the parallel subset")
    if not q.answerable and q.parallel_group:
        err("unanswerable queries stay out of the parallel subset")

    # Country signals (§7).
    implied = implied_countries(q.query)
    if q.country and implied and q.country not in implied:
        warn(f"country {q.country} but the query mentions {'/'.join(sorted(implied))}")
    if q.country is None and len(implied) == 1 and q.answerable:
        warn(f"country is null but the query implies {next(iter(implied))}")
    if q.type == QueryType.AMBIGUOUS and implied:
        err(f"ambiguous query implies {'/'.join(sorted(implied))}; set country")

    # Gold chunks (§5, §6).
    gold = []
    for cid in q.gold_chunk_ids:
        if cid not in chunks:
            err(f"unknown chunk {cid}")
        else:
            gold.append(chunks[cid])
    if len(set(q.gold_chunk_ids)) != len(q.gold_chunk_ids):
        err("duplicate gold chunk")
    if q.type == QueryType.MULTI_HOP and not 2 <= len(q.gold_chunk_ids) <= 3:
        err("multi_hop needs 2 or 3 gold chunks")
    for c in gold:
        if c.superseded and not q.about_old_policy:
            err(f"{c.chunk_id} is superseded; it can't be gold for current policy")
        if not c.superseded and q.about_old_policy:
            warn(f"about_old_policy, but {c.chunk_id} is current")
        if q.country and q.country not in c.countries:
            err(f"{c.chunk_id} doesn't cover {q.country} (covers {', '.join(c.countries)})")
    trap = q.type == QueryType.SUPERSEDED_TRAP and q.answerable
    if trap and not any(c.has_old_edition for c in gold):
        warn("superseded_trap, but no gold chunk is from an article with an old edition")

    # Critical facts must be quoted from a gold chunk (§9).
    bodies = [norm(c.body) for c in gold]
    for fact in q.critical_facts:
        if not any(norm(fact) in b for b in bodies):
            err(f"critical fact {fact!r} isn't in any gold chunk body")


def _check_parallel(sources: list[QuerySource], err, warn) -> None:
    groups: dict[str, list[QuerySource]] = defaultdict(list)
    for q in sources:
        if q.parallel_group:
            groups[q.parallel_group].append(q)
    for pg, members in sorted(groups.items()):
        varieties = Counter(q.variety for q in members)
        for v, n in varieties.items():
            if n > 1:
                err(pg, f"{n} queries in variety {v}")
        if missing := PARALLEL_VARIETIES - set(varieties):
            warn(pg, f"missing varieties: {', '.join(sorted(missing))}")
        first = members[0]
        for q in members[1:]:
            for f in ("gold_chunk_ids", "country", "type", "reference_answer", "critical_facts"):
                a, b = getattr(first, f), getattr(q, f)
                if (sorted(a) if isinstance(a, list) else a) != (
                    sorted(b) if isinstance(b, list) else b
                ):
                    err(pg, f"{q.qid} differs from {first.qid} in {f}")


def _check_chunk_load(sources: list[QuerySource], warn) -> None:
    # Distinct intents per chunk: a parallel group counts once.
    intents: dict[str, set[str]] = defaultdict(set)
    for q in sources:
        for cid in q.gold_chunk_ids:
            intents[cid].add(q.parallel_group or q.qid)
    for cid, ids in sorted(intents.items()):
        if len(ids) > MAX_INTENTS_PER_CHUNK:
            warn(cid, f"gold for {len(ids)} intents (max {MAX_INTENTS_PER_CHUNK})")


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "–"


def render_stats(queries: list[Query]) -> str:
    n = len(queries)
    answerable = [q for q in queries if q.answerable and not q.needs_clarification]
    ambiguous = [q for q in queries if q.needs_clarification]
    unans = [q for q in queries if not q.answerable]
    parallel = [q for q in queries if q.parallel_group]
    rest = [q for q in queries if not q.parallel_group]
    groups = Counter(q.parallel_group for q in parallel)
    complete = sum(1 for c in groups.values() if c == len(PARALLEL_VARIETIES))
    gsrc = Counter(q.gold_source for q in answerable)

    lines = [
        "# Evaluation set statistics",
        "",
        "Generated by `python -m musaid.benchmark.build`. Don't edit by hand.",
        "",
        "| | Count | Share | Target |",
        "|---|---|---|---|",
        f"| Queries | {n} | | ≥450 |",
        f"| Answerable (clear) | {len(answerable)} | {_pct(len(answerable), n)} | |",
        f"| Ambiguous | {len(ambiguous)} | {_pct(len(ambiguous), n)} | ~8% |",
        f"| Unanswerable | {len(unans)} | {_pct(len(unans), n)} | 10–15% |",
        f"| Parallel groups complete | {complete} of {len(groups)} | | 40 |",
        "",
        "## Gold source (ADR-010, answerable and clear only)",
        "",
        "| Source | Count | Share | Target |",
        "|---|---|---|---|",
    ]
    for src, target in (("rewritten", "~70%"), ("draft", "~30%"), ("mixed", "")):
        lines.append(f"| {src} | {gsrc[src]} | {_pct(gsrc[src], len(answerable))} | {target} |")

    by_var_all = Counter(q.variety for q in queries)
    by_var_rest = Counter(q.variety for q in rest)
    lines += [
        "",
        "## Varieties",
        "",
        "| Variety | All | Outside parallel subset | Share outside | Target |",
        "|---|---|---|---|---|",
    ]
    for v, share in VARIETY_TARGET_SHARE.items():
        lines.append(
            f"| {v} | {by_var_all[v]} | {by_var_rest[v]} | "
            f"{_pct(by_var_rest[v], len(rest))} | {share:.0%} |"
        )

    by_type = Counter(q.type for q in queries)
    lines += ["", "## Query types", "", "| Type | Count | Share |", "|---|---|---|"]
    for t in QueryType:
        lines.append(f"| {t} | {by_type[t]} | {_pct(by_type[t], n)} |")

    by_country = Counter(q.country or "none" for q in queries)
    lines += ["", "## Country", "", "| Country | Count |", "|---|---|"]
    for c in ("SA", "AE", "EG", "none"):
        lines.append(f"| {c} | {by_country[c]} |")
    return "\n".join(lines) + "\n"


def _jsonl(records) -> str:
    return "".join(
        json.dumps(r.model_dump(mode="json"), ensure_ascii=False) + "\n" for r in records
    )


def build(root: Path, final: bool = False) -> tuple[BenchResult, dict[Path, str]]:
    chunks = load_chunks(root)
    raws, issues = load_sources(root / "data" / "eval" / "source")
    res = check_queries(raws, chunks)
    res.issues[:0] = issues
    eval_dir = root / "data" / "eval"
    split_path = eval_dir / "split.json"
    if split_path.exists():
        split = json.loads(split_path.read_text(encoding="utf-8"))
        res.queries = [q.model_copy(update={"split": split.get(q.qid)}) for q in res.queries]
        for q in res.queries:
            if q.split is None:
                res.issues.append(
                    Issue(
                        "warning",
                        q.qid,
                        "no split yet: run `python -m musaid.benchmark.split assign`",
                    )
                )
        for qid in sorted(set(split) - {q.qid for q in res.queries}):
            res.issues.append(Issue("error", qid, "in split.json but no longer in the sources"))
    if final:  # before locking: unverified labels and incomplete groups must be fixed
        res.issues = [
            Issue("error", i.where, f"final: {i.message}") if i.level == "warning" else i
            for i in res.issues
        ]
    outputs = {
        eval_dir / "queries.jsonl": _jsonl(res.queries),
        root / "docs" / "EVAL_STATS.md": render_stats(res.queries),
    }
    if split_path.exists():
        for name in ("dev", "test"):
            outputs[eval_dir / f"{name}.jsonl"] = _jsonl(q for q in res.queries if q.split == name)
        lock_path = eval_dir / "test.lock.json"
        if lock_path.exists():
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            test_jsonl = outputs[eval_dir / "test.jsonl"]
            for problem in verify_lock(lock, test_jsonl, chunk_hashes(root)):
                res.issues.append(Issue("error", "test.lock.json", problem))
    return res, outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m musaid.benchmark.build")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true", help="fail on errors or stale outputs")
    parser.add_argument("--final", action="store_true", help="warnings and unverified fail too")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    res, outputs = build(args.root, final=args.final)
    for issue in res.issues:
        print(issue)
    print(f"\n{len(res.queries)} queries, {len(res.errors)} errors, {len(res.warnings)} warnings")
    if res.errors:
        return 1
    stale = []
    for path, content in outputs.items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        rel = path.relative_to(args.root).as_posix()
        if args.check:
            stale.append(rel)
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
            print(f"wrote {rel}")
    if stale:
        print(f"Stale outputs (run the build and commit): {', '.join(stale)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
