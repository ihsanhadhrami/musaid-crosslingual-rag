"""Build the published KB from source articles and facts.csv.

uv run python -m musaid.ingest.build             # write kb.jsonl, chunks.jsonl, KB_STATS.md
uv run python -m musaid.ingest.build --check     # CI: fail on errors or stale outputs
uv run python -m musaid.ingest.build sample 30   # print random chunks for hand inspection
"""

import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path

from musaid.ingest.articles import load_articles, load_inventory
from musaid.ingest.chunking import chunk_article
from musaid.ingest.facts import load_facts
from musaid.ingest.schema import Chunk
from musaid.ingest.stats import render_stats
from musaid.ingest.validate import KBResult, check_kb

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class Paths:
    root: Path

    @property
    def kb_dir(self) -> Path:
        return self.root / "data" / "kb"

    @property
    def outputs(self) -> dict[str, Path]:
        return {
            "kb": self.kb_dir / "kb.jsonl",
            "chunks": self.kb_dir / "chunks.jsonl",
            "stats": self.root / "docs" / "KB_STATS.md",
        }


def _jsonl(records) -> str:
    return "".join(r.model_dump_json() + "\n" for r in records)


def build(paths: Paths) -> tuple[KBResult, list[Chunk], dict[str, str]]:
    facts = load_facts(paths.kb_dir / "facts.csv")
    inventory = load_inventory(paths.kb_dir / "inventory.csv")
    sources = load_articles(paths.kb_dir / "articles")
    result = check_kb(sources, facts, set(inventory))
    chunks = [c for a in result.articles for c in chunk_article(a)]
    outputs = {
        "kb": _jsonl(result.articles),
        "chunks": _jsonl(chunks),
        "stats": render_stats(sources, facts, result, chunks, planned=len(inventory)),
    }
    return result, chunks, outputs


def _cmd_build(paths: Paths, check: bool) -> int:
    result, chunks, outputs = build(paths)
    for issue in result.issues:
        print(issue)
    print(
        f"\n{len(result.articles)} articles, {len(chunks)} chunks, "
        f"{len(result.errors)} errors, {len(result.warnings)} warnings"
    )
    if result.errors:
        return 1

    stale = []
    for key, content in outputs.items():
        path = paths.outputs[key]
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        if check:
            stale.append(path.relative_to(paths.root).as_posix())
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
            print(f"wrote {path.relative_to(paths.root).as_posix()}")
    if stale:
        print(f"Stale outputs (run the build and commit): {', '.join(stale)}")
        return 1
    return 0


def _cmd_sample(paths: Paths, n: int, seed: int) -> int:
    _, chunks, _ = build(paths)
    for c in random.Random(seed).sample(chunks, min(n, len(chunks))):
        print(f"=== {c.chunk_id}  ({c.n_tokens} tokens, {', '.join(c.countries)})")
        print(c.text)
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m musaid.ingest.build")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true", help="fail on errors or stale outputs")
    sub = parser.add_subparsers(dest="cmd")
    sample = sub.add_parser("sample", help="print random chunks for hand inspection")
    sample.add_argument("n", type=int, nargs="?", default=30)
    sample.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")
    paths = Paths(args.root)
    if args.cmd == "sample":
        return _cmd_sample(paths, args.n, args.seed)
    return _cmd_build(paths, args.check)


if __name__ == "__main__":
    raise SystemExit(main())
