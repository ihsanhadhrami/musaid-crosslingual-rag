"""Run one retrieval configuration on a split and save the result.

uv run python -m musaid.evaluation.run bm25_raw              # dev (default)
uv run python -m musaid.evaluation.run bm25_raw --split test # only once test.lock.json exists

Results go to eval/results/<config>__<split>.json with the config, git commit, timing,
metrics (overall and by variety, type, gold source, parallel group) and per-query ranks.
"""

import argparse
import sys
import time
from pathlib import Path

from musaid.evaluation.harness import RunResult, load_split, save, scored, timed

ROOT = Path(__file__).resolve().parents[3]

TRANSLATOR = {"model": "deepseek-flash", "prompt_version": "v1"}
BM25 = {"retriever": "bm25", "k1": 1.5, "b": 0.75}
BGE_M3 = {"retriever": "dense", "model": "BAAI/bge-m3", "max_seq_length": 512}

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
    "dense_e5_large_raw": {
        "name": "dense_e5_large_raw",
        "description": "Ablation #3: dense intfloat/multilingual-e5-large on the raw query",
        "retriever": "dense",
        "model": "intfloat/multilingual-e5-large",
        "query": "raw",
        "max_seq_length": 512,
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
        "k": 100,
    },
    "bm25_translated": {
        "name": "bm25_translated",
        "description": "Ablation #4: translate Arabic queries to English (DeepSeek), then BM25",
        "retriever": "bm25",
        "query": "translated",
        "translator": TRANSLATOR,
        "k1": 1.5,
        "b": 0.75,
        "k": 100,
    },
    "dense_bge_m3_translated": {
        "name": "dense_bge_m3_translated",
        "description": "Diagnostic for #5: translate (DeepSeek), then dense bge-m3 only",
        **BGE_M3,
        "query": "translated",
        "translator": TRANSLATOR,
        "k": 100,
    },
    "hybrid_translated": {
        "name": "hybrid_translated",
        "description": "Ablation #5: translate (DeepSeek), then BM25 + dense bge-m3, fused by RRF",
        "retriever": "fusion",
        "routes": [
            {**BM25, "query": "translated", "translator": TRANSLATOR},
            {**BGE_M3, "query": "translated", "translator": TRANSLATOR},
        ],
        "rrf_k": 60,
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
            query_prefix=config.get("query_prefix", ""),
            passage_prefix=config.get("passage_prefix", ""),
        )
    raise ValueError(f"unknown retriever {config['retriever']!r}")


def query_texts(config: dict, queries, root: Path) -> tuple[list[str], dict | None]:
    """The text each query is searched with, and translation stats when translated."""
    raw = [q.query for q in queries]
    if config["query"] == "raw":
        return raw, None
    if config["query"] != "translated":
        raise ValueError(f"unknown query mode {config['query']!r}")
    from musaid.config import get_settings
    from musaid.translate.llm import (
        DeepSeekTranslator,
        TranslationCache,
        translate_all,
        translation_stats,
    )

    tr = config["translator"]
    cache = TranslationCache(
        root / "eval" / "translations" / f"{tr['model']}__{tr['prompt_version']}.jsonl"
    )

    def make():
        s = get_settings()
        return DeepSeekTranslator(
            s.deepseek_api_key.get_secret_value(), model=tr["model"], base_url=s.deepseek_base_url
        )

    texts, records = translate_all(raw, cache, tr["model"], tr["prompt_version"], make)
    stats = translation_stats(records)
    stats["texts"] = {q.qid: t for q, t, r in zip(queries, texts, records, strict=True) if r}
    return texts, stats


def retrieve(retriever, config: dict, texts: list[str], queries) -> dict[str, dict[str, float]]:
    hits = retriever.search(texts, k=config["k"])
    return {q.qid: h for q, h in zip(queries, hits, strict=True)}


def run_config(config: dict, queries, root: Path) -> tuple[dict, float, float, dict | None]:
    """Rankings, query seconds, index seconds and translation stats for one config.

    A fusion config runs each route (its own retriever and query text) and fuses them by
    RRF. Query seconds add up over routes, as if they ran one after another.
    """
    if config["retriever"] != "fusion":
        texts, translation = query_texts(config, queries, root)
        retriever, index_seconds = timed(build_retriever, config, root)
        rankings, seconds = timed(retrieve, retriever, config, texts, queries)
        return rankings, seconds, index_seconds, translation

    from musaid.retrieval.fusion import rrf

    per_route, seconds, index_seconds, translation = [], 0.0, 0.0, None
    for route in config["routes"]:
        route = {**route, "k": config["k"]}
        r, s, i, t = run_config(route, queries, root)
        per_route.append(r)
        seconds, index_seconds = seconds + s, index_seconds + i
        translation = translation or t  # every translated route shares one cache
    t0 = time.perf_counter()
    fused = {
        q.qid: rrf([r[q.qid] for r in per_route], k=config["rrf_k"], depth=config["k"])
        for q in queries
    }
    return fused, seconds + time.perf_counter() - t0, index_seconds, translation


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
    rankings, seconds, index_seconds, translation = run_config(config, queries, args.root)
    result = RunResult(
        config=config,
        split=args.split,
        rankings=rankings,
        seconds=seconds,
        index_seconds=index_seconds,
        translation=translation,
    )
    out = save(args.root, result, queries)

    import json

    metrics = json.loads(out.read_text(encoding="utf-8"))["metrics"]
    print(f"{config['description']}  [{args.split}, {len(scored(queries))} scored queries]\n")
    print(format_table(metrics))
    if translation:
        t = {k: v for k, v in translation.items() if k != "texts"}
        print(f"\ntranslation: {t}")
    print(f"\nwrote {out.relative_to(args.root).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
