"""Phone/tablet-friendly PDF of the review sheet (used by `review --pdf`).

Renders HTML and prints it with headless Edge or Chrome, which shape Arabic and lay out
right-to-left text correctly (ReportLab doesn't). One card per parallel group, with its
six queries together and the gold shown once, or one card per single query.
"""

import html
import re
import subprocess
from collections import defaultdict
from pathlib import Path

from musaid.benchmark.build import ChunkInfo

BROWSERS = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path("/usr/bin/chromium"),
    Path("/usr/bin/google-chrome"),
]
VARIETY_ORDER = ["english", "msa", "gulf", "levantine_egyptian", "code_switched", "arabizi"]

CSS = """
@page { size: A5; margin: 9mm 8mm; }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", "Noto Naskh Arabic", "Arial", sans-serif; font-size: 10pt;
       line-height: 1.45; color: #1a1a1a; margin: 0; }
h1 { font-size: 15pt; margin: 0 0 4pt; }
.intro { font-size: 9pt; color: #444; margin-bottom: 8pt; }
.card { border: 1px solid #c9c9c9; border-radius: 6px; padding: 7pt 8pt; margin: 0 0 9pt; }
.head, .q, .label, .facts, .check { break-inside: avoid; }
.head, .label { break-after: avoid; }
.head { display: flex; flex-wrap: wrap; gap: 4pt; align-items: baseline; margin-bottom: 5pt; }
.id { font-weight: 700; font-size: 11pt; }
.tag { font-size: 8pt; background: #eef1f5; border-radius: 3px; padding: 0 4pt; }
.tag.warn { background: #fde7c4; }
.file { font-size: 7.5pt; color: #777; margin-left: auto; }
.q { margin: 3pt 0; padding: 3pt 6pt; background: #f7f7f7; border-radius: 4px; }
.q .v { font-size: 7.5pt; color: #666; display: block; }
.q .t { font-size: 11.5pt; unicode-bidi: plaintext; }
.label { font-size: 7.5pt; font-weight: 700; color: #555; text-transform: uppercase;
         letter-spacing: .03em; margin-top: 6pt; }
.gold { font-size: 8.5pt; border-left: 3px solid #9bb8d3; padding: 2pt 6pt; margin: 3pt 0; }
.gold b { font-size: 8.5pt; }
.answer { font-size: 9.5pt; }
.facts span { display: inline-block; font-size: 8.5pt; border: 1px solid #b7c7b0;
              background: #f1f7ee; border-radius: 3px; padding: 0 4pt; margin: 1pt 2pt 0 0; }
.warnbox { font-size: 8pt; background: #fff6e6; border-radius: 4px; padding: 3pt 6pt;
           margin-top: 5pt; }
.notes { font-size: 8pt; color: #555; margin-top: 4pt; }
.check { margin-top: 6pt; font-size: 9pt; color: #333; border-top: 1px dashed #ccc;
         padding-top: 4pt; }
"""


def find_browser() -> Path | None:
    return next((p for p in BROWSERS if p.exists()), None)


def _e(text: str) -> str:
    return html.escape(str(text or ""))


def _body(c: ChunkInfo, n: int) -> str:
    text = re.sub(r"\s+", " ", c.body.replace("**", "")).strip()
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " …"


def _units(raws: list[dict]) -> list[list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    units: list[list[dict]] = []
    for r in raws:
        if pg := r.get("parallel_group"):
            if pg not in groups:
                units.append(groups[pg])
            groups[pg].append(r)
        else:
            units.append([r])
    for u in units:
        u.sort(key=lambda r: VARIETY_ORDER.index(r["variety"]) if r["variety"] in VARIETY_ORDER
               else 99)  # fmt: skip
    return units


def render_html(
    raws: list[dict],
    chunks: dict[str, ChunkInfo],
    files: dict[str, str],
    competitors,
    title: str,
    excerpt: int = 900,
) -> str:
    cards = []
    for unit in _units(raws):
        first = unit[0]
        label = first.get("parallel_group") or first["qid"]
        qids = f"{unit[0]['qid']}–{unit[-1]['qid']}" if len(unit) > 1 else first["qid"]
        tags = [first["type"], first.get("country") or "no country"]
        if not first.get("answerable", True):
            tags.append(f"unanswerable: {first.get('unanswerable_reason')}")
        if first.get("needs_clarification"):
            tags.append("needs clarification")
        if first.get("about_old_policy"):
            tags.append("asks about old policy")
        head = (
            f'<div class="head"><span class="id">{_e(label)}</span>'
            + (f'<span class="tag">{_e(qids)}</span>' if len(unit) > 1 else "")
            + "".join(f'<span class="tag">{_e(t)}</span>' for t in tags)
            + f'<span class="file">{_e(files.get(first["qid"], ""))}</span></div>'
        )
        queries = "".join(
            f'<div class="q"><span class="v">{_e(r["qid"])} · {_e(r["variety"])} · '
            f'{_e(r.get("difficulty", ""))}</span><span class="t" dir="auto">{_e(r["query"])}'
            "</span></div>"
            for r in unit
        )
        parts = [head, queries]
        if first.get("answerable", True):
            golds = []
            for cid in first.get("gold_chunk_ids", []):
                c = chunks.get(cid)
                body = _e(_body(c, excerpt)) if c else "(unknown chunk)"
                flags = []
                if c and c.superseded:
                    flags.append("SUPERSEDED")
                if c:
                    flags.append("rewritten" if c.rewritten else "draft")
                golds.append(
                    f'<div class="gold"><b>{_e(cid)}</b> · {_e(c.title if c else "")} '
                    f"({_e(', '.join(c.countries) if c else '')}; {_e(', '.join(flags))})<br>"
                    f"{body}</div>"
                )
            facts = first.get("critical_facts") or []
            parts += [
                '<div class="label">Gold chunks</div>',
                *golds,
                '<div class="label">Reference answer</div>',
                f'<div class="answer">{_e(first.get("reference_answer", "").strip())}</div>',
                '<div class="label">Critical facts</div>',
                '<div class="facts">'
                + ("".join(f"<span>{_e(f)}</span>" for f in facts) or "<i>(none)</i>")
                + "</div>",
            ]
            comps = competitors(first, chunks)
            if comps:
                others = "; ".join(f"{c.chunk_id} {c.title}" for c in comps)
                parts.append(f'<div class="warnbox">⚠ Also contains the facts: {_e(others)}</div>')
        if first.get("notes"):
            parts.append(f'<div class="notes">Notes: {_e(first["notes"].strip())}</div>')
        parts.append('<div class="check">☐ OK &nbsp;&nbsp; ☐ Fix: ______________________</div>')
        cards.append(f'<div class="card">{"".join(parts)}</div>')

    intro = (
        f"{len(raws)} queries in {len(cards)} cards. For each card: does every query sound like "
        "a real customer, does each gold chunk fully answer it, are the facts right? Make the "
        "fixes in the YAML file named on the card, then set <code>verified: true</code>."
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{_e(title)}</title><style>{CSS}</style></head><body>"
        f'<h1>{_e(title)}</h1><div class="intro">{intro}</div>{"".join(cards)}</body></html>'
    )


def print_pdf(html_path: Path, pdf_path: Path) -> None:
    browser = find_browser()
    if browser is None:
        raise RuntimeError("No Edge or Chrome found; open the .html file and print it to PDF.")
    subprocess.run(
        [
            str(browser),
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            html_path.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=300,
    )
