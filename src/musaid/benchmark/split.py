"""Dev/test split and test-set lock (ANNOTATION.md §13, spec Phase 2 step 6).

uv run python -m musaid.benchmark.split assign     # write data/eval/split.json (new queries only)
uv run python -m musaid.benchmark.split lock       # after review: hash test.jsonl + gold chunks
uv run python -m musaid.benchmark.build            # applies split.json, writes dev/test files

Rules:
- A parallel group, and any queries tied with `split_with`, move as one unit.
- 275 queries go to test, the rest to dev, stratified with a fixed seed: parallel groups
  by query type, single queries by (variety, type).
- Assignments are append-only: rerunning `assign` keeps every existing qid where it is.
- Once test.lock.json exists, the build fails if test.jsonl or any of its gold chunks change.
"""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from musaid.benchmark.schema import Query

TEST_SIZE = 275
SEED = "musaid-2026"


def _h(key: str) -> str:
    return hashlib.sha256(f"{SEED}:{key}".encode()).hexdigest()


def units_of(queries: list[Query], ties: dict[str, str]) -> dict[str, list[Query]]:
    """Group queries into split units: parallel group, or a `split_with` chain, or itself."""
    parent = {q.qid: q.qid for q in queries}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    by_group: dict[str, list[str]] = defaultdict(list)
    for q in queries:
        if q.parallel_group:
            by_group[q.parallel_group].append(q.qid)
    for members in by_group.values():
        for m in members[1:]:
            parent[find(m)] = find(members[0])
    for a, b in ties.items():
        if a in parent and b in parent:
            parent[find(a)] = find(b)

    units: dict[str, list[Query]] = defaultdict(list)
    for q in queries:
        units[find(q.qid)].append(q)
    return dict(units)


def _stratum(unit: list[Query]) -> str:
    first = unit[0]
    if first.parallel_group:  # types are balanced by interleaving (see _ordered)
        return f"parallel:{first.gold_source}"
    # varieties are balanced by interleaving inside the stratum
    return f"single:{first.type}:{first.gold_source}"


def _ordered(units: list[list[Query]], stratum: str) -> list[list[Query]]:
    """Order units so any prefix samples each sub-group in proportion to its size.

    Sub-groups are query types for parallel units and varieties for single queries.
    """
    sub = (
        (lambda u: str(u[0].type))
        if stratum.startswith("parallel")
        else (lambda u: str(u[0].variety))
    )
    by_sub: dict[str, list[list[Query]]] = defaultdict(list)
    for u in sorted(units, key=lambda u: _h(min(q.qid for q in u))):
        by_sub[sub(u)].append(u)
    # Proportional interleave: unit i of a sub-group with n units sits at (i + 0.5) / n,
    # so taking the first k units samples every sub-group in proportion to its size.
    keyed = [
        ((i + 0.5) / len(us), _h(f"{stratum}:{k}"), u)
        for k, us in by_sub.items()
        for i, u in enumerate(us)
    ]
    out = [u for _, _, u in sorted(keyed, key=lambda t: (t[0], t[1]))]
    return out


def _allocate(sizes: dict[str, int], target: int) -> dict[str, int]:
    """Largest-remainder allocation of `target` across strata, proportional to size."""
    total = sum(sizes.values())
    if total == 0:
        return {s: 0 for s in sizes}
    raw = {s: n * target / total for s, n in sizes.items()}
    out = {s: int(v) for s, v in raw.items()}
    rest = target - sum(out.values())
    for s in sorted(raw, key=lambda s: (-(raw[s] - out[s]), _h(s)))[:rest]:
        out[s] += 1
    return out


def assign(
    queries: list[Query], existing: dict[str, str], ties: dict[str, str], test_size: int = TEST_SIZE
) -> dict[str, str]:
    """Return {qid: "dev" | "test"} for every query, keeping existing assignments.

    New queries join their unit's existing split if a member already has one; otherwise
    new units are split so that the total test count gets as close to test_size as possible.
    """
    units = units_of(queries, ties)
    out = dict(existing)
    fresh: list[list[Query]] = []
    for unit in units.values():
        known = {existing[q.qid] for q in unit if q.qid in existing}
        if len(known) > 1:
            raise ValueError(f"unit {[q.qid for q in unit]} is split across dev and test")
        if known:
            for q in unit:
                out[q.qid] = next(iter(known))
        else:
            fresh.append(unit)

    test_now = sum(1 for v in out.values() if v == "test")
    want = max(0, min(test_size - test_now, sum(len(u) for u in fresh)))

    # Allocate in units of queries: parallel units are 6 queries, singles 1.
    families: dict[str, list[list[Query]]] = defaultdict(list)
    for u in fresh:
        families["parallel" if u[0].parallel_group else "single"].append(u)
    n_fresh = sum(len(u) for u in fresh)
    for fam, fam_units in sorted(families.items()):
        fam_q = sum(len(u) for u in fam_units)
        size = len(fam_units[0]) if fam == "parallel" else 1
        fam_target = round(want * fam_q / n_fresh / size) if n_fresh else 0
        if fam == "single":  # singles absorb rounding so the total is exact
            already = sum(1 for v in out.values() if v == "test") - test_now
            fam_target = max(0, min(len(fam_units), want - already))
        strata: dict[str, list[list[Query]]] = defaultdict(list)
        for u in fam_units:
            strata[_stratum(u)].append(u)
        quota = _allocate({s: len(us) for s, us in strata.items()}, fam_target)
        for s, us in strata.items():
            for i, u in enumerate(_ordered(us, s)):
                for q in u:
                    out[q.qid] = "test" if i < quota[s] else "dev"

    # Multi-query single units (split_with ties) can overshoot; move one-query fresh units.
    fresh_singles = sorted(
        (u for u in fresh if not u[0].parallel_group and len(u) == 1),
        key=lambda u: _h(u[0].qid),
    )
    goal = test_now + want
    count = sum(1 for q in queries if out[q.qid] == "test")
    for u in fresh_singles:
        if count == goal:
            break
        q = u[0]
        if count > goal and out[q.qid] == "test":
            out[q.qid], count = "dev", count - 1
        elif count < goal and out[q.qid] == "dev":
            out[q.qid], count = "test", count + 1
    return {q.qid: out[q.qid] for q in queries}


def chunk_hashes(root: Path) -> dict[str, str]:
    lines = (root / "data" / "kb" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    return {c["chunk_id"]: c["body_sha1"] for c in map(json.loads, lines)}


def make_lock(test_jsonl: str, test: list[Query], hashes: dict[str, str]) -> dict:
    gold = sorted({c for q in test for c in q.gold_chunk_ids})
    return {
        "locked_on": date.today().isoformat(),
        "queries": len(test),
        "sha256": hashlib.sha256(test_jsonl.encode()).hexdigest(),
        "gold_chunks": {c: hashes[c] for c in gold},
        "note": "Don't edit. To change a test label: write an ADR, then rerun the lock.",
    }


def verify_lock(lock: dict, test_jsonl: str, hashes: dict[str, str]) -> list[str]:
    problems = []
    if hashlib.sha256(test_jsonl.encode()).hexdigest() != lock["sha256"]:
        problems.append("test.jsonl changed after the lock (write an ADR, then re-lock)")
    for cid, sha in lock["gold_chunks"].items():
        if hashes.get(cid) != sha:
            problems.append(f"gold chunk {cid} changed or disappeared since the lock")
    return problems


def _paths(root: Path) -> dict[str, Path]:
    d = root / "data" / "eval"
    return {"split": d / "split.json", "test": d / "test.jsonl", "lock": d / "test.lock.json"}


def main(argv: list[str] | None = None) -> int:
    from musaid.benchmark.build import ROOT, build, load_sources

    parser = argparse.ArgumentParser(prog="python -m musaid.benchmark.split")
    parser.add_argument("cmd", choices=["assign", "lock"])
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    p = _paths(args.root)

    if args.cmd == "assign":
        res, _ = build(args.root)
        if res.errors:
            print("Fix build errors first.")
            return 1
        raws, _ = load_sources(args.root / "data" / "eval" / "source")
        ties = {r["qid"]: r["split_with"] for _, r in raws if r.get("split_with")}
        existing = json.loads(p["split"].read_text(encoding="utf-8")) if p["split"].exists() else {}
        if p["lock"].exists() and any(q.qid not in existing for q in res.queries):
            print("Test set is locked: new queries go to dev only.")
            existing = existing | {q.qid: "dev" for q in res.queries if q.qid not in existing}
        split = assign(res.queries, existing, ties)
        text = json.dumps(split, indent=0, sort_keys=True) + "\n"
        p["split"].write_text(text, encoding="utf-8", newline="\n")
        n_test = sum(v == "test" for v in split.values())
        print(f"wrote {p['split'].name}: {n_test} test, {len(split) - n_test} dev")
        print("Now run: python -m musaid.benchmark.build")
        return 0

    # lock
    if p["lock"].exists():
        print("Already locked. Changing the test set needs an ADR; delete the lock deliberately.")
        return 1
    res, outputs = build(args.root, final=True)
    if res.errors:
        for i in res.errors[:20]:
            print(i)
        print(f"\n{len(res.errors)} errors under --final: verify every query before locking.")
        return 1
    test_jsonl = outputs.get(p["test"])
    if test_jsonl is None or test_jsonl != p["test"].read_text(encoding="utf-8"):
        print("Run `split assign` and `build` first, so test.jsonl is current.")
        return 1
    test = [q for q in res.queries if q.split == "test"]
    lock = make_lock(test_jsonl, test, chunk_hashes(args.root))
    p["lock"].write_text(json.dumps(lock, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"locked {len(test)} test queries ({lock['sha256'][:12]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
