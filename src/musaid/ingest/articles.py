"""Source article and inventory loading."""

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from musaid.ingest.schema import COUNTRIES, ArticleMeta

FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.S)
# Cross-reference syntax in source: [Visible title](kb-0042). Rendered as the title only.
DOC_LINK = re.compile(r"\[([^\]]+)\]\((kb-\d{4})\)")


class ArticleError(ValueError):
    pass


@dataclass(frozen=True)
class SourceArticle:
    path: Path
    meta: ArticleMeta
    body: str


def parse_article(raw: str, name: str = "<article>", path: Path | None = None) -> SourceArticle:
    m = FRONT_MATTER.match(raw)
    if not m:
        raise ArticleError(f"{name}: missing '---' front matter")
    data = yaml.safe_load(m.group(1)) or {}
    if data.get("countries") == "all":
        data["countries"] = list(COUNTRIES)
    try:
        meta = ArticleMeta.model_validate(data)
    except ValidationError as e:
        raise ArticleError(f"{name}: {e}") from e
    return SourceArticle(path=path or Path(name), meta=meta, body=m.group(2).strip() + "\n")


def load_articles(directory: Path) -> list[SourceArticle]:
    return [
        parse_article(p.read_text(encoding="utf-8"), p.name, p)
        for p in sorted(directory.glob("*.md"))
    ]


def load_inventory(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return {row["doc_id"]: row for row in csv.DictReader(f)}


def linked_doc_ids(body: str) -> list[str]:
    return [m.group(2) for m in DOC_LINK.finditer(body)]


def strip_links(body: str) -> str:
    return DOC_LINK.sub(r"\1", body)
