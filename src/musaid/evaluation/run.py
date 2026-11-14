"""Run one retrieval configuration on a split and save the result.

uv run python -m musaid.evaluation.run bm25_raw              # dev (default)
uv run python -m musaid.evaluation.run bm25_raw --split test # only once test.lock.json exists

Results go to eval/results/<config>__<split>.json with the config, git commit, timing,
metrics (overall and by variety, type, gold source, parallel group) and per-query ranks.
"""

import argparse
import sys
from pathlib import Path

from musaid.evaluation.harness import RunResult, load_split, save, scored, timed

ROOT = Path(__file__).resolve().parents[3]

CONFIGS: dict[str, dict] = {
    "bm25_raw": {
        "name": "bm25_raw",
        "description": "Baseline A: BM25 (bm25s, English stemmer) on the raw query",
        "retriever": "bm25",
        "query": "raw",
        "k1": 1.5,
        "b": 0.75,
        "k": 100,
    },
    "dense_bge_m3_raw": {
        "name": "dense_bge_m3_raw",
        "description": "Baseline B: dense BAAI/bge-m3 on the raw query (direct cross-lingual)",
        "retriever": "dense",
        "model": "BAAI/bge-m3",
        "query": "raw",
        "max_seq_length": 512,
        "k": 100,
    },
}


def build_retriever(config: dict, root: Path):
    from musaid.retrieval.bm25 import load_chunks

    chunks = load_chunks(root)
    if config["retriever"] == "bm25":
        from musaid.retrieval.bm25 import BM25Retriever

        return BM25Retriever(chunks, k1=config["k1"], b=config["b"])
    if config["retriever"] == "dense":
        from musaid.retrieval.dense import DenseRetriever

        return DenseRetriever(
            chunks,
            model_name=config["model"],
            cache_dir=root / "data" / "cache",
            max_seq_length=config["max_seq_length"],
        )
    raise ValueError(f"unknown retriever {config['retriever']!r}")


def retrieve(retriever, config: dict, queries) -> dict[str, dict[str, float]]:
    hits = retriever.search([q.query for q in queries], k=config["k"])
    return {q.qid: h for q, h in zip(queries, hits, strict=True)}


def format_table(metrics: dict) -> str:
    cols = ["n", "recall@10", "mrr@10", "ndcg@10"]
    lines = [f"{'':24}" + "".join(f"{c:>11}" for c in cols)]

    def row(label, m):
        cells = "".join(f"{m.get(c, 0):>11}" if c == "n" else f"{m.get(c, 0):>11.3f}" for c in cols)
        lines.append(f"{label:24}{cells}")

    row("overall", metrics["overall"])
    for section in ("variety", "type", "gold_source", "parallel_by_variety"):
        lines.append(f"-- {section}")
        for k, m in metrics[section].items():
            row(f"  {k}", m)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m musaid.evaluation.run")
    parser.add_argument("config", choices=sorted(CONFIGS))
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    if args.split == "test" and not (args.root / "data" / "eval" / "test.lock.json").exists():
        print("The test set isn't locked yet (ADR-012). Tune and compare on dev only.")
        return 1
    config = CONFIGS[args.config]
    queries = load_split(args.root, args.split)
    retriever, index_seconds = timed(build_retriever, config, args.root)
    rankings, seconds = timed(retrieve, retriever, config, queries)
    result = RunResult(
        config=config,
        split=args.split,
        rankings=rankings,
        seconds=seconds,
        index_seconds=index_seconds,
    )
    out = save(args.root, result, queries)

    import json

    metrics = json.loads(out.read_text(encoding="utf-8"))["metrics"]
    print(f"{config['description']}  [{args.split}, {len(scored(queries))} scored queries]\n")
    print(format_table(metrics))
    print(f"\nwrote {out.relative_to(args.root).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
