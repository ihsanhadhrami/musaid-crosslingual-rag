"""Build data/glossary/glossary.jsonl from the hand-written YAML sources.

uv run python -m musaid.glossary.build            # validate and write glossary.jsonl
uv run python -m musaid.glossary.build --check    # CI: fail on errors or a stale output
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

from musaid.glossary.schema import ARABIC_SCRIPT_VARIETIES, VARIETIES, GlossaryEntry
from musaid.ingest.validate import Issue

ROOT = Path(__file__).resolve().parents[3]

_ARABIC_LETTER = re.compile(r"[ء-ي]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")
# Arabizi: lowercase Latin letters and the usual digit letters (2 3 5 6 7 8 9).
_ARABIZI = re.compile(r"^[a-z0-9]+(?:[ '-][a-z0-9]+)*$")
_DIACRITICS = re.compile(r"[ً-ْٰـ]")  # harakat, dagger alef, tatweel
_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و"})


def fold_arabic(text: str) -> str:
    """Light orthographic folding so near-identical spellings count as duplicates."""
    return _DIACRITICS.sub("", text).translate(_FOLD)


def fold_english(text: str) -> str:
    text = text.replace("’", "'").replace("**", "").lower()
    return re.sub(r"\s+", " ", text)


@dataclass
class GlossaryResult:
    entries: list[GlossaryEntry] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]


def load_sources(src_dir: Path) -> tuple[list[tuple[str, dict]], list[Issue]]:
    """Read every *.yaml file; each holds a list of entries. Returns (where, raw) pairs."""
    raws, issues = [], []
    for path in sorted(src_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(data, list):
            issues.append(Issue("error", path.name, "file must hold a YAML list of entries"))
            continue
        for i, raw in enumerate(data):
            cid = raw.get("concept_id", f"#{i}") if isinstance(raw, dict) else f"#{i}"
            raws.append((f"{path.name}:{cid}", raw))
    return raws, issues


def check_glossary(raws: list[tuple[str, dict]], kb_text: str) -> GlossaryResult:
    res = GlossaryResult()

    def err(where: str, msg: str) -> None:
        res.issues.append(Issue("error", where, msg))

    def warn(where: str, msg: str) -> None:
        res.issues.append(Issue("warning", where, msg))

    for where, raw in raws:
        try:
            res.entries.append(GlossaryEntry.model_validate(raw))
        except ValidationError as e:
            for d in e.errors():
                err(where, f"{'.'.join(map(str, d['loc']))}: {d['msg']}")

    for key, n in Counter(e.concept_id for e in res.entries).items():
        if n > 1:
            err(key, f"concept_id used by {n} entries")
    for key, n in Counter(e.kb_term.lower() for e in res.entries).items():
        if n > 1:
            err(key, f"kb_term used by {n} entries; merge them or pick a narrower term")

    kb = fold_english(kb_text)
    # variety -> folded form -> concept ids, to spot one phrase mapped to two concepts.
    seen: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    for e in res.entries:
        where = e.concept_id
        for term in (e.kb_term, *e.kb_aliases):
            t = fold_english(term)
            if not re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", kb):
                err(where, f"KB term {term!r} doesn't appear in the KB")
        for variety, forms in e.variants.items():
            folded_here = Counter()
            for form in forms:
                if form != form.strip() or "  " in form:
                    err(where, f"{variety} {form!r}: stray whitespace")
                if variety in ARABIC_SCRIPT_VARIETIES:
                    if not _ARABIC_LETTER.search(form) or _LATIN_LETTER.search(form):
                        err(where, f"{variety} {form!r}: must be Arabic script only")
                    key = fold_arabic(form)
                else:
                    if not _ARABIZI.match(form):
                        err(where, f"arabizi {form!r}: use lowercase Latin letters and digits")
                    key = form
                folded_here[key] += 1
                seen[variety][key].append(e.concept_id)
            for key, n in folded_here.items():
                if n > 1:
                    err(where, f"{variety} {key!r} listed {n} times")

    for variety in VARIETIES:
        for form, cids in seen[variety].items():
            owners = sorted(set(cids))
            if len(owners) > 1:
                warn(
                    form,
                    f"{variety} form shared by {', '.join(owners)} (ambiguous; fine if intended)",
                )
    return res


def render_jsonl(entries: list[GlossaryEntry]) -> str:
    rows = sorted(entries, key=lambda e: (e.category, e.concept_id))
    return "".join(json.dumps(e.model_dump(), ensure_ascii=False) + "\n" for e in rows)


def summarize(entries: list[GlossaryEntry]) -> str:
    by_cat = Counter(e.category for e in entries)
    forms = {v: sum(len(getattr(e.variants, v)) for e in entries) for v in VARIETIES}
    lines = [f"{len(entries)} entries, {sum(forms.values())} variant forms"]
    lines.append("  by variety:  " + ", ".join(f"{v} {n}" for v, n in forms.items()))
    lines.append("  by category: " + ", ".join(f"{c} {n}" for c, n in sorted(by_cat.items())))
    return "\n".join(lines)


def build(root: Path) -> tuple[GlossaryResult, str]:
    raws, issues = load_sources(root / "data" / "glossary" / "source")
    kb_lines = (root / "data" / "kb" / "kb.jsonl").read_text(encoding="utf-8").splitlines()
    kb_text = "\n".join(json.loads(line)["text"] for line in kb_lines if line)
    res = check_glossary(raws, kb_text)
    res.issues[:0] = issues
    return res, render_jsonl(res.entries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m musaid.glossary.build")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true", help="fail on errors or a stale output")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    res, content = build(args.root)
    for issue in res.issues:
        print(issue)
    print(f"\n{summarize(res.entries)}\n{len(res.errors)} errors, {len(res.warnings)} warnings")
    if res.errors:
        return 1

    out = args.root / "data" / "glossary" / "glossary.jsonl"
    current = out.read_text(encoding="utf-8") if out.exists() else None
    if current == content:
        return 0
    if args.check:
        print("Stale output (run the build and commit): data/glossary/glossary.jsonl")
        return 1
    out.write_text(content, encoding="utf-8", newline="\n")
    print("wrote data/glossary/glossary.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
