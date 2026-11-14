"""Retrieval evaluation harness (spec Phase 3 step 1).

run_retrieval(config) -> rankings -> ranx metrics, broken down by variety, query type,
gold source and parallel group. Only queries with gold chunks are scored: answerable
ones and ambiguous ones (their gold holds the per-country answers). Unanswerable queries
are left for the escalation metrics in later phases.
"""

import json
import subprocess
import time
import warnings
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

warnings.filterwarnings("ignore", category=SyntaxWarning, module="ranx")  # LaTeX strings in ranx
warnings.filterwarnings("ignore", message=".*unsafe cast.*")  # numba, harmless here

from ranx import Qrels, Run, evaluate  # noqa: E402

from musaid.benchmark.schema import Query  # noqa: E402

METRICS = ["recall@5", "recall@10", "recall@20", "mrr@10", "ndcg@10"]
SLICES = ("variety", "type", "gold_source")


@dataclass(frozen=True)
class RunResult:
    config: dict
    split: str
    rankings: dict[str, dict[str, float]]
    seconds: float  # query-time only: encoding + search for every query in the split
    index_seconds: float = 0.0  # building or loading the index (one-off, not per query)


def load_split(root: Path, split: str) -> list[Query]:
    path = root / "data" / "eval" / f"{split}.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Query.model_validate_json(line) for line in lines if line]


def scored(queries: list[Query]) -> list[Query]:
    return [q for q in queries if q.gold_chunk_ids]


def _qrels(queries: list[Query]) -> Qrels:
    return Qrels({q.qid: {c: 1 for c in q.gold_chunk_ids} for q in queries})


def _run(queries: list[Query], rankings: dict[str, dict[str, float]], name: str) -> Run:
    # ranx needs an entry per query; a query with no hits gets a sentinel zero-score doc.
    return Run(
        {q.qid: (rankings.get(q.qid) or {"__none__": 0.0}) for q in queries},
        name=name,
    )


def metrics_for(queries: list[Query], rankings: dict[str, dict[str, float]]) -> dict:
    if not queries:
        return {"n": 0}
    res = evaluate(_qrels(queries), _run(queries, rankings, "r"), METRICS)
    return {"n": len(queries), **{m: round(float(v), 4) for m, v in res.items()}}


def per_query(queries: list[Query], rankings: dict[str, dict[str, float]]) -> dict[str, dict]:
    out = {}
    for q in queries:
        ranked = sorted(rankings.get(q.qid, {}).items(), key=lambda x: -x[1])
        ids = [c for c, _ in ranked]
        gold = set(q.gold_chunk_ids)
        first = next((i + 1 for i, c in enumerate(ids) if c in gold), None)
        out[q.qid] = {
            "first_gold_rank": first,
            "recall@10": round(len(gold & set(ids[:10])) / len(gold), 4),
            "top5": ids[:5],
        }
    return out


def breakdown(queries: list[Query], rankings: dict[str, dict[str, float]]) -> dict:
    out: dict = {"overall": metrics_for(queries, rankings)}
    for field in SLICES:
        groups: dict[str, list[Query]] = defaultdict(list)
        for q in queries:
            groups[str(getattr(q, field))].append(q)
        out[field] = {k: metrics_for(v, rankings) for k, v in sorted(groups.items())}
    parallel = [q for q in queries if q.parallel_group]
    by_var: dict[str, list[Query]] = defaultdict(list)
    for q in parallel:
        by_var[str(q.variety)].append(q)
    out["parallel_by_variety"] = {k: metrics_for(v, rankings) for k, v in sorted(by_var.items())}
    pq = per_query(parallel, rankings)
    matrix: dict[str, dict[str, float]] = defaultdict(dict)
    for q in parallel:
        matrix[q.parallel_group][str(q.variety)] = pq[q.qid]["recall@10"]
    out["parallel_group_recall@10"] = dict(sorted(matrix.items()))
    return out


def git_sha(root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True
        ).stdout.strip()
    except OSError:
        return "unknown"


def save(root: Path, result: RunResult, queries: list[Query]) -> Path:
    ids = scored(queries)
    payload = {
        "config": result.config,
        "split": result.split,
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "git": git_sha(root),
        "queries_total": len(queries),
        "queries_scored": len(ids),
        "index_seconds": round(result.index_seconds, 2),
        "seconds": round(result.seconds, 2),
        "ms_per_query": round(1000 * result.seconds / max(len(queries), 1), 2),
        "metrics": breakdown(ids, result.rankings),
        "per_query": per_query(ids, result.rankings),
    }
    out = root / "eval" / "results" / f"{result.config['name']}__{result.split}.json"
    out.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                   newline="\n")  # fmt: skip
    return out


def timed(fn, *args):
    t0 = time.perf_counter()
    value = fn(*args)
    return value, time.perf_counter() - t0
