"""Validate source articles against facts.csv and each other; render published articles."""

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

from musaid.ingest.articles import SourceArticle, linked_doc_ids, strip_links
from musaid.ingest.facts import PLACEHOLDER, render
from musaid.ingest.schema import Article, Fact

# Governed values must come from facts.csv, never be typed into an article.
LITERAL_MONEY = re.compile(r"\b(?:SAR|AED|EGP)\s?\d|\d[\d,.]*\s?%")
# Durations are usually governed too, but some are harmless ("within 24 hours" in a tip).
LITERAL_DURATION = re.compile(
    r"\b\d+\s+(?:business\s+|calendar\s+|working\s+)?"
    r"(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b",
    re.I,
)


@dataclass(frozen=True)
class Issue:
    level: Literal["error", "warning"]
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():7} {self.where}: {self.message}"


@dataclass
class KBResult:
    articles: list[Article] = field(default_factory=list)
    facts_used: dict[str, list[str]] = field(default_factory=dict)  # doc_id -> fact ids
    links: dict[str, list[str]] = field(default_factory=dict)  # doc_id -> linked doc ids
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]


def check_kb(sources: list[SourceArticle], facts: dict[str, Fact], planned: set[str]) -> KBResult:
    res = KBResult()

    def err(where: str, msg: str) -> None:
        res.issues.append(Issue("error", where, msg))

    def warn(where: str, msg: str) -> None:
        res.issues.append(Issue("warning", where, msg))

    by_id = {s.meta.doc_id: s for s in sources}
    for doc_id, n in Counter(s.meta.doc_id for s in sources).items():
        if n > 1:
            err(doc_id, f"doc_id used by {n} files")

    for src in sources:
        meta, where = src.meta, src.meta.doc_id
        stem = src.path.stem
        if stem != meta.doc_id and not stem.startswith(meta.doc_id + "-"):
            err(where, f"file name {src.path.name!r} must start with the doc_id")
        if meta.doc_id not in planned:
            err(where, "not in inventory.csv")
        if re.search(r"^# ", src.body, re.M):
            warn(where, "body has an H1; the title comes from front matter, start at ##")

        # Facts
        rendered, used, unknown = render(src.body, facts)
        for fid in unknown:
            err(where, f"unknown fact {{{{{fid}}}}}")
        for fid in dict.fromkeys(used):
            fact = facts[fid]
            if fact.superseded_by and meta.superseded_by is None:
                err(where, f"current article uses superseded fact {fid}")
            if fact.effective_date > meta.effective_date:
                err(where, f"uses {fid} (effective {fact.effective_date}) before it takes effect")
            if fact.country != "ALL" and fact.country not in meta.countries:
                err(where, f"uses {fid} but countries is {meta.countries}")
        res.facts_used[meta.doc_id] = list(dict.fromkeys(used))

        # Values typed in by hand instead of {{fact}} placeholders
        bare = PLACEHOLDER.sub("", src.body)
        for m in LITERAL_MONEY.finditer(bare):
            err(where, f"literal amount {m.group(0)!r}; use a {{{{fact}}}} placeholder")
        for m in LITERAL_DURATION.finditer(bare):
            warn(where, f"literal duration {m.group(0)!r}; use a fact if it's a policy value")

        # Cross-references and supersession
        links = linked_doc_ids(src.body)
        res.links[meta.doc_id] = links
        for target in links:
            _check_ref(where, "links to", target, by_id, planned, err, warn)
        if meta.superseded_by:
            _check_ref(where, "superseded_by", meta.superseded_by, by_id, planned, err, warn)
            newer = by_id.get(meta.superseded_by)
            if newer and newer.meta.effective_date <= meta.effective_date:
                err(where, f"replacement {newer.meta.doc_id} must have a later effective_date")

        res.articles.append(
            Article(
                doc_id=meta.doc_id,
                title=meta.title,
                category=meta.category,
                section_path=meta.section_path,
                countries=meta.countries,
                effective_date=meta.effective_date,
                superseded_by=meta.superseded_by,
                article_type=meta.article_type,
                text=strip_links(rendered).strip(),
            )
        )

    res.articles.sort(key=lambda a: a.doc_id)
    return res


def _check_ref(where, label, target, by_id, planned, err, warn) -> None:
    if target in by_id:
        return
    if target in planned:
        warn(where, f"{label} {target}, which is planned but not drafted yet")
    else:
        err(where, f"{label} {target}, which is not in inventory.csv")
