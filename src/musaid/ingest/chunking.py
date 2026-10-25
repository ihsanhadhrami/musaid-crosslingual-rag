"""Structure-aware chunking (spec Phase 1 step 5).

Rules:
- Split on ##/### headings; adjacent sections are packed together until a chunk reaches
  MIN_TOKENS (short trailing sections still join), never beyond MAX_TOKENS.
- Never split a table or a list (procedures); a paragraph ending in ':' stays with the list
  or table it introduces. An atomic block bigger than MAX_TOKENS becomes its own chunk.
- Sections whose heading names a country (e.g. "## Egypt") get that country as chunk
  metadata, and are never packed with sections for other countries.
- Every chunk's `text` is prefixed with title, section path and countries.
"""

import hashlib
import re
from dataclasses import dataclass, field

from musaid.ingest.schema import COUNTRIES, COUNTRY_NAMES, Article, Chunk, Country

CHUNKER_VERSION = "1"
MAX_TOKENS = 400
MIN_TOKENS = 200  # stop packing sections once a chunk reaches this size

# Rough proxy for subword tokens (words + punctuation). Good enough for sizing chunks;
# swap in the bge-m3 tokenizer if exact counts are ever needed.
_TOKEN = re.compile(r"\w+|[^\w\s]")
_HEADING = re.compile(r"^(#{2,6})\s+(.*\S)\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_COUNTRY_IN_HEADING: dict[Country, re.Pattern[str]] = {
    "SA": re.compile(r"\b(?:saudi|ksa)\b", re.I),
    "AE": re.compile(r"\b(?:uae|emirates)\b", re.I),
    "EG": re.compile(r"\begypt", re.I),
}


def count_tokens(text: str) -> int:
    return len(_TOKEN.findall(text))


@dataclass
class Block:
    kind: str  # heading | para | list | table
    text: str
    level: int = 0


@dataclass
class Section:
    headings: list[str]
    countries: tuple[Country, ...] | None
    pieces: list[str] = field(default_factory=list)
    has_content: bool = False


def heading_countries(heading: str) -> tuple[Country, ...] | None:
    found = tuple(c for c in COUNTRIES if _COUNTRY_IN_HEADING[c].search(heading))
    return found or None


def _is_table(line: str) -> bool:
    return line.lstrip().startswith("|")


def parse_blocks(md: str) -> list[Block]:
    blocks: list[Block] = []
    group: list[str] = []

    def flush() -> None:
        if not group:
            return
        if _is_table(group[0]):
            kind = "table"
        elif _LIST_ITEM.match(group[0]):
            kind = "list"
        else:
            kind = "para"
        blocks.append(Block(kind, "\n".join(group)))
        group.clear()

    for line in md.splitlines():
        if not line.strip():
            flush()
            continue
        if m := _HEADING.match(line):
            flush()
            blocks.append(Block("heading", m.group(2), len(m.group(1))))
            continue
        if group and _is_table(line) != _is_table(group[-1]):
            flush()
        group.append(line)
    flush()
    return _merge_atomic(blocks)


def _merge_atomic(blocks: list[Block]) -> list[Block]:
    """Join list items split by blank lines, and attach 'lead-in:' paragraphs."""
    out: list[Block] = []
    for b in blocks:
        prev = out[-1] if out else None
        if prev and b.kind in ("list", "table"):
            same_list = prev.kind == "list" and b.kind == "list"
            lead_in = prev.kind == "para" and prev.text.rstrip().endswith(":")
            if same_list or lead_in:
                out[-1] = Block(b.kind, f"{prev.text}\n\n{b.text}")
                continue
        out.append(b)
    return out


def split_sections(blocks: list[Block]) -> list[Section]:
    sections = [Section(headings=[], countries=None)]
    stack: list[tuple[int, str]] = []
    for b in blocks:
        if b.kind == "heading":
            while stack and stack[-1][0] >= b.level:
                stack.pop()
            stack.append((b.level, b.text))
            heads = [h for _, h in stack]
            countries = next((c for h in reversed(heads) if (c := heading_countries(h))), None)
            sections.append(Section(heads, countries, [f"{'#' * b.level} {b.text}"]))
        else:
            sections[-1].pieces.append(b.text)
            sections[-1].has_content = True
    return [s for s in sections if s.has_content]


@dataclass
class _Group:
    sections: list[Section]
    pieces: list[str]

    @property
    def countries(self) -> tuple[Country, ...] | None:
        return self.sections[0].countries

    @property
    def tokens(self) -> int:
        return count_tokens("\n\n".join(self.pieces))


def _pack(sections: list[Section], max_tokens: int, min_tokens: int) -> list[_Group]:
    groups: list[_Group] = []
    cur: _Group | None = None
    for s in sections:
        s_tokens = count_tokens("\n\n".join(s.pieces))
        if s_tokens > max_tokens:
            if cur:
                groups.append(cur)
                cur = None
            groups.extend(_split_section(s, max_tokens))
            continue
        # Keep packing while the chunk is small; a short section (e.g. a closing note)
        # also joins the previous chunk rather than becoming an orphan.
        if (
            cur
            and cur.countries == s.countries
            and (cur.tokens < min_tokens or s_tokens < min_tokens // 2)
            and cur.tokens + s_tokens <= max_tokens
        ):
            cur.sections.append(s)
            cur.pieces.extend(s.pieces)
        else:
            if cur:
                groups.append(cur)
            cur = _Group([s], list(s.pieces))
    if cur:
        groups.append(cur)
    return groups


def _split_section(s: Section, max_tokens: int) -> list[_Group]:
    groups: list[_Group] = []
    pieces: list[str] = []
    for piece in s.pieces:
        if pieces and count_tokens("\n\n".join([*pieces, piece])) > max_tokens:
            groups.append(_Group([s], pieces))
            pieces = []
        pieces.append(piece)
    if pieces:
        groups.append(_Group([s], pieces))
    return groups


def _prefix(title: str, section_path: list[str], countries: list[Country]) -> str:
    names = ", ".join(COUNTRY_NAMES[c] for c in countries)
    return f"{title}\nSection: {' > '.join(section_path)}\nCountries: {names}\n\n"


def chunk_article(
    article: Article, max_tokens: int = MAX_TOKENS, min_tokens: int = MIN_TOKENS
) -> list[Chunk]:
    sections = split_sections(parse_blocks(article.text))
    chunks: list[Chunk] = []
    for i, g in enumerate(_pack(sections, max_tokens, min_tokens)):
        headed = [s.headings for s in g.sections if s.headings]
        section_path = list(article.section_path)
        if len(g.sections) == 1 and headed:
            section_path += headed[0]
        countries = list(g.countries or article.countries)
        body = "\n\n".join(g.pieces)
        text = _prefix(article.title, section_path, countries) + body
        chunks.append(
            Chunk(
                chunk_id=f"{article.doc_id}#c{i}",
                doc_id=article.doc_id,
                chunk_index=i,
                title=article.title,
                category=article.category,
                article_type=article.article_type,
                section_path=section_path,
                headings=[" > ".join(h) for h in headed],
                countries=countries,
                effective_date=article.effective_date,
                superseded_by=article.superseded_by,
                text=text,
                body=body,
                n_tokens=count_tokens(text),
                body_sha1=hashlib.sha1(body.encode("utf-8")).hexdigest()[:12],
            )
        )
    return chunks
