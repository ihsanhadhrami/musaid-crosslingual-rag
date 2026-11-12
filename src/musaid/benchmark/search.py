"""Search helper for labeling gold chunks (ANNOTATION.md §5). Use it to *find* candidates;
read each chunk in full before labeling it.

uv run python -m musaid.benchmark.search "dispute deadline card payment"
uv run python -m musaid.benchmark.search "transfer limit" --country SA -k 15
uv run python -m musaid.benchmark.search --show kb-0077#c0 kb-0071#c2

This is a plain BM25 over English chunk text, kept separate from the retrieval code under
test so labeling never depends on the system being evaluated.
"""

import argparse
import math
import re
import sys
from collections import Counter
from pathlib import Path

from musaid.benchmark.build import ROOT, ChunkInfo, load_chunks

_TOKEN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")
_STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "for",
        "from",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "my",
        "of",
        "on",
        "or",
        "our",
        "the",
        "this",
        "to",
        "was",
        "we",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "you",
        "your",
    }
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower().replace("’", "'")) if t not in _STOP]


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tfs = [Counter(d) for d in docs]
        self.lens = [len(d) for d in docs]
        self.avg = sum(self.lens) / max(len(docs), 1)
        df = Counter(t for d in docs for t in set(d))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for tf, n in zip(self.tfs, self.lens, strict=True):
            s = 0.0
            for t in query:
                if f := tf.get(t):
                    s += (
                        self.idf[t]
                        * f
                        * (self.k1 + 1)
                        / (f + self.k1 * (1 - self.b + self.b * n / self.avg))
                    )
            out.append(s)
        return out


def search(
    chunks: dict[str, ChunkInfo], query: str, k: int = 10, country: str | None = None
) -> list[tuple[float, ChunkInfo]]:
    items = [c for c in chunks.values() if country is None or country in c.countries]
    index = BM25([tokenize(f"{c.title} {c.body}") for c in items])
    ranked = sorted(zip(index.scores(tokenize(query)), items, strict=True), key=lambda x: -x[0])
    return [(s, c) for s, c in ranked[:k] if s > 0]


def _flags(c: ChunkInfo) -> str:
    flags = ["rewritten" if c.rewritten else "draft"]
    if c.superseded:
        flags.append("SUPERSEDED")
    if c.has_old_edition:
        flags.append("has-old-edition")
    return ", ".join(flags)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m musaid.benchmark.search")
    parser.add_argument("query", nargs="*", help="English search words")
    parser.add_argument("-k", type=int, default=10)
    parser.add_argument("--country", choices=["SA", "AE", "EG"])
    parser.add_argument("--show", nargs="+", metavar="CHUNK_ID", help="print chunks in full")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    chunks = load_chunks(args.root)

    if args.show:
        for cid in args.show:
            c = chunks.get(cid)
            if c is None:
                print(f"=== {cid}: no such chunk")
                continue
            print(f"=== {cid}  {c.title}  [{', '.join(c.countries)}; {_flags(c)}]\n")
            print(c.body, "\n")
        return 0
    if not args.query:
        parser.error("give search words or --show")

    for score, c in search(chunks, " ".join(args.query), args.k, args.country):
        snippet = re.sub(r"\s+", " ", c.body)[:110]
        print(f"{score:6.2f}  {c.chunk_id:12} {c.title}  [{', '.join(c.countries)}; {_flags(c)}]")
        print(f"        {snippet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
