"""Glossary validation rules, and the committed glossary must build cleanly."""

from musaid.glossary.build import ROOT, build, check_glossary, fold_arabic

KB = "You can request a refund. Refund fees are listed below. Your balance updates."


def entry(**overrides):
    raw = {
        "concept_id": "refund",
        "kb_term": "refund",
        "category": "refunds_disputes",
        "variants": {
            "msa": ["استرداد"],
            "gulf": ["ترجع فلوسي"],
            "levantine_egyptian": ["ترجيع الفلوس"],
            "arabizi": ["arja3 floosi"],
        },
    }
    raw.update(overrides)
    return raw


def messages(raws, kb=KB):
    res = check_glossary([(r.get("concept_id", "?"), r) for r in raws], kb)
    return res, [i.message for i in res.errors], [i.message for i in res.warnings]


def test_valid_entry_passes():
    res, errors, warnings = messages([entry()])
    assert errors == [] and warnings == []
    assert len(res.entries) == 1


def test_kb_term_must_appear_in_kb_as_a_whole_word():
    _, errors, _ = messages([entry(kb_term="chargeback")])
    assert any("doesn't appear" in m for m in errors)
    _, errors, _ = messages([entry(kb_term="fund")])  # inside "refund" only
    assert any("doesn't appear" in m for m in errors)


def test_every_variety_needs_a_form():
    raw = entry()
    raw["variants"]["arabizi"] = []
    _, errors, _ = messages([raw])
    assert any("arabizi" in m for m in errors)


def test_script_rules():
    raw = entry()
    raw["variants"]["gulf"] = ["refund حقي"]
    raw["variants"]["arabizi"] = ["Arja3 Floosi"]
    _, errors, _ = messages([raw])
    assert any("Arabic script only" in m for m in errors)
    assert any("lowercase Latin" in m for m in errors)


def test_duplicates_after_folding_are_errors_within_an_entry():
    raw = entry()
    raw["variants"]["msa"] = ["إسترداد", "استرداد"]
    _, errors, _ = messages([raw])
    assert any("listed 2 times" in m for m in errors)


def test_shared_form_across_entries_is_a_warning():
    other = entry(concept_id="balance", kb_term="balance", category="general")
    _, errors, warnings = messages([entry(), other])
    assert errors == []
    assert any("shared by balance, refund" in m for m in warnings)


def test_duplicate_concept_id_and_kb_term():
    _, errors, _ = messages([entry(), entry()])
    assert any("concept_id used by 2" in m for m in errors)
    assert any("kb_term used by 2" in m for m in errors)


def test_fold_arabic():
    assert fold_arabic("إستردادٌ") == fold_arabic("استرداد")
    assert fold_arabic("فاتورة") == "فاتوره"


def test_committed_glossary_is_clean_and_current():
    res, content = build(ROOT)
    assert [str(e) for e in res.errors] == []
    assert len(res.entries) >= 150, "spec §5.3 needs at least 150 glossary entries"
    path = ROOT / "data" / "glossary" / "glossary.jsonl"
    assert path.read_text(encoding="utf-8") == content, (
        "glossary.jsonl is stale: run `uv run python -m musaid.glossary.build`"
    )
