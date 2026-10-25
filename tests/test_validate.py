from datetime import date
from textwrap import dedent

import pytest

from musaid.ingest.articles import parse_article
from musaid.ingest.schema import Fact
from musaid.ingest.validate import check_kb

FACTS = {
    f.fact_id: f
    for f in [
        Fact(
            fact_id="fees.x.SA",
            topic="fees.x",
            country="SA",
            value="1.5",
            unit="percent",
            display="1.5%",
            effective_date=date(2026, 3, 1),
        ),
        Fact(
            fact_id="fees.x.SA@2025-01-01",
            topic="fees.x",
            country="SA",
            value="2",
            unit="percent",
            display="2%",
            effective_date=date(2025, 1, 1),
            superseded_by="fees.x.SA",
        ),
        Fact(
            fact_id="fees.x.AE",
            topic="fees.x",
            country="AE",
            value="1",
            unit="percent",
            display="1%",
            effective_date=date(2025, 1, 1),
        ),
    ]
}


def article(body: str, doc_id="kb-0001", countries="[SA]", effective="2026-03-01", **extra):
    fm = {
        "doc_id": doc_id,
        "title": "Test",
        "category": "fees_limits",
        "section_path": "[Fees]",
        "countries": countries,
        "effective_date": effective,
        "article_type": "fee_table",
        **extra,
    }
    head = "\n".join(f"{k}: {v}" for k, v in fm.items())
    return parse_article(f"---\n{head}\n---\n{dedent(body)}", name=f"{doc_id}.md")


def errors(*sources, planned=("kb-0001", "kb-0002", "kb-0003")):
    return [i.message for i in check_kb(list(sources), FACTS, set(planned)).errors]


def test_clean_article_renders():
    res = check_kb(
        [article("Fee: {{fees.x.SA}}. See [Other](kb-0002).")], FACTS, {"kb-0001", "kb-0002"}
    )
    assert not res.errors
    assert res.articles[0].text == "Fee: 1.5%. See Other."
    assert [w.message for w in res.warnings] == [
        "links to kb-0002, which is planned but not drafted yet"
    ]


@pytest.mark.parametrize("body", ["Costs SAR 20 per transfer.", "Costs 2% of the amount."])
def test_literal_amounts_are_errors(body):
    assert any("literal amount" in e for e in errors(article(body)))


def test_literal_duration_is_warning():
    res = check_kb([article("Arrives in 3 business days.")], FACTS, {"kb-0001"})
    assert not res.errors
    assert "literal duration" in res.warnings[0].message


def test_unknown_fact():
    assert any("unknown fact" in e for e in errors(article("{{fees.nope.SA}}")))


def test_current_article_cannot_use_superseded_fact():
    assert any("superseded fact" in e for e in errors(article("{{fees.x.SA@2025-01-01}}")))


def test_fact_must_be_effective_by_article_date():
    found = errors(article("{{fees.x.SA}}", effective="2025-01-01"))
    assert any("before it takes effect" in e for e in found)


def test_fact_country_must_match_article():
    assert any("countries" in e for e in errors(article("{{fees.x.AE}}", countries="[SA]")))


def test_supersession_chain():
    old = article(
        "{{fees.x.SA@2025-01-01}}",
        doc_id="kb-0002",
        effective="2025-01-01",
        superseded_by="kb-0001",
    )
    assert errors(article("{{fees.x.SA}}"), old) == []

    backwards = article("x", doc_id="kb-0002", effective="2027-01-01", superseded_by="kb-0001")
    assert any("later effective_date" in e for e in errors(article("x"), backwards))


def test_unplanned_and_duplicate_ids():
    assert any("inventory" in e for e in errors(article("x", doc_id="kb-0009")))
    assert any("used by 2 files" in e for e in errors(article("x"), article("y")))
