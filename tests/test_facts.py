from pathlib import Path

import pytest

from musaid.ingest.facts import FactsError, load_facts, render

HEADER = "fact_id,topic,country,value,unit,display,effective_date,superseded_by,notes\n"


def write_facts(tmp_path: Path, rows: str) -> Path:
    path = tmp_path / "facts.csv"
    path.write_text(HEADER + rows, encoding="utf-8")
    return path


def test_load_and_render(tmp_path):
    facts = load_facts(
        write_facts(
            tmp_path,
            'fees.x.SA,fees.x,SA,1000,SAR,"SAR 1,000",2025-01-01,,\n'
            "otp.ALL,otp,ALL,5,minutes,5 minutes,2025-01-01,,\n",
        )
    )
    text, used, unknown = render("Fee {{fees.x.SA}}, code valid {{ otp.ALL }}, {{nope.SA}}", facts)
    assert text == "Fee SAR 1,000, code valid 5 minutes, {{nope.SA}}"
    assert used == ["fees.x.SA", "otp.ALL"]
    assert unknown == ["nope.SA"]


def test_superseded_fact_needs_dated_id_and_later_replacement(tmp_path):
    ok = (
        "fees.x.SA@2025-01-01,fees.x,SA,2,percent,2%,2025-01-01,fees.x.SA,\n"
        "fees.x.SA,fees.x,SA,1.5,percent,1.5%,2026-03-01,,\n"
    )
    assert len(load_facts(write_facts(tmp_path, ok))) == 2

    undated = "fees.x.SA,fees.x,SA,2,percent,2%,2025-01-01,fees.y.SA,\n"
    with pytest.raises(FactsError, match="should be"):
        load_facts(write_facts(tmp_path, undated))


def test_fact_id_must_match_topic_and_country(tmp_path):
    with pytest.raises(FactsError, match=r"should be 'fees.x.AE'"):
        load_facts(write_facts(tmp_path, "fees.x.SA,fees.x,AE,1,AED,AED 1,2025-01-01,,\n"))


def test_duplicate_fact(tmp_path):
    row = "fees.x.SA,fees.x,SA,1,SAR,SAR 1,2025-01-01,,\n"
    with pytest.raises(FactsError, match="duplicate"):
        load_facts(write_facts(tmp_path, row * 2))


def test_real_facts_file_loads():
    facts = load_facts(Path(__file__).parents[1] / "data" / "kb" / "facts.csv")
    assert len(facts) > 100
