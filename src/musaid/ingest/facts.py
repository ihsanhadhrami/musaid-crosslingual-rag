"""facts.csv loading and {{fact_id}} placeholder rendering."""

import csv
import re
from pathlib import Path

from pydantic import ValidationError

from musaid.ingest.schema import Fact

PLACEHOLDER = re.compile(r"\{\{\s*([^{}\s]+)\s*\}\}")


class FactsError(ValueError):
    pass


def load_facts(path: Path) -> dict[str, Fact]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    facts: dict[str, Fact] = {}
    for line_no, row in enumerate(rows, start=2):
        clean = {k: (v or "").strip() for k, v in row.items()}
        clean["superseded_by"] = clean.get("superseded_by") or None
        try:
            fact = Fact.model_validate(clean)
        except ValidationError as e:
            raise FactsError(f"{path.name} line {line_no}: {e}") from e
        if fact.fact_id != fact.expected_id:
            raise FactsError(
                f"{path.name} line {line_no}: fact_id {fact.fact_id!r} "
                f"should be {fact.expected_id!r} (topic.country[@effective_date if superseded])"
            )
        if fact.fact_id in facts:
            raise FactsError(f"{path.name} line {line_no}: duplicate fact_id {fact.fact_id!r}")
        facts[fact.fact_id] = fact

    for fact in facts.values():
        if fact.superseded_by is None:
            continue
        newer = facts.get(fact.superseded_by)
        if newer is None:
            raise FactsError(f"{fact.fact_id}: superseded_by {fact.superseded_by!r} not found")
        if newer.effective_date <= fact.effective_date:
            raise FactsError(f"{fact.fact_id}: replacement must have a later effective_date")
    return facts


def render(text: str, facts: dict[str, Fact]) -> tuple[str, list[str], list[str]]:
    """Replace {{fact_id}} with the fact's display value.

    Returns (rendered text, fact ids used, unknown ids). Unknown placeholders are left as-is.
    """
    used: list[str] = []
    unknown: list[str] = []

    def sub(m: re.Match[str]) -> str:
        fact = facts.get(m.group(1))
        if fact is None:
            unknown.append(m.group(1))
            return m.group(0)
        used.append(fact.fact_id)
        return fact.display

    return PLACEHOLDER.sub(sub, text), used, unknown
