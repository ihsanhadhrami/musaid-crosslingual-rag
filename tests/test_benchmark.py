"""Query validation rules (docs/ANNOTATION.md) and the search helper."""

from musaid.benchmark.build import ROOT, ChunkInfo, build, check_queries, implied_countries
from musaid.benchmark.search import search

REFUND_BODY = "Refunds take 5 business days in Saudi Arabia."


def chunk(cid, countries=("SA", "AE", "EG"), *, rewritten=True, superseded=False, old=False,
          body=REFUND_BODY, title="Refund timelines"):  # fmt: skip
    return ChunkInfo(
        chunk_id=cid,
        doc_id=cid.split("#")[0],
        title=title,
        countries=tuple(countries),
        superseded=superseded,
        rewritten=rewritten,
        has_old_edition=old,
        body=body,
    )


CHUNKS = {
    c.chunk_id: c
    for c in [
        chunk("kb-0071#c0", old=True),
        chunk("kb-0073#c0", ("AE",), superseded=True, body="Refunds take 14 days."),
        chunk("kb-0200#c0", rewritten=False, body="Card disputes: 60 calendar days."),
        chunk("kb-0300#c0", ("EG",), rewritten=False, body="InstaPay transfers are instant."),
    ]
}


def q(**overrides):
    raw = {
        "qid": "q-0001",
        "query": "How long until my refund comes back?",
        "variety": "english",
        "type": "number_sensitive",
        "country": "SA",
        "gold_chunk_ids": ["kb-0071#c0"],
        "reference_answer": "Refunds take 5 business days in Saudi Arabia.",
        "critical_facts": ["5 business days"],
        "difficulty": "easy",
        "verified": True,
    }
    raw.update(overrides)
    return raw


def run(*raws):
    res = check_queries([(r["qid"], r) for r in raws], CHUNKS)
    return res, [i.message for i in res.errors], [i.message for i in res.warnings]


def test_valid_query_passes_and_derives_fields():
    res, errors, warnings = run(q())
    assert errors == [] and warnings == []
    (out,) = res.queries
    assert out.script == "latin" and out.gold_source == "rewritten"


def test_variety_must_match_script():
    _, errors, _ = run(q(variety="gulf"))
    assert any("Latin letters" in m for m in errors)
    _, errors, _ = run(q(variety="code_switched", query="ابي اسوي refund"))
    assert errors == []
    _, errors, _ = run(q(variety="code_switched", query="ابي ارجع فلوسي"))
    assert any("code_switched" in m for m in errors)


def test_superseded_chunk_is_never_gold_for_current_policy():
    _, errors, _ = run(q(country="AE", gold_chunk_ids=["kb-0073#c0"], critical_facts=[]))
    assert any("superseded" in m for m in errors)
    _, errors, _ = run(
        q(country="AE", gold_chunk_ids=["kb-0073#c0"], critical_facts=[], about_old_policy=True)
    )
    assert errors == []


def test_gold_chunk_must_cover_the_country():
    _, errors, _ = run(q(country="SA", gold_chunk_ids=["kb-0300#c0"], critical_facts=[]))
    assert any("doesn't cover SA" in m for m in errors)


def test_critical_facts_are_quoted_from_gold():
    _, errors, _ = run(q(critical_facts=["7 business days"]))
    assert any("isn't in any gold chunk" in m for m in errors)


def test_unanswerable_rules():
    base = {"answerable": False, "type": "unanswerable", "gold_chunk_ids": [],
            "critical_facts": [], "reference_answer": "", "country": None}  # fmt: skip
    _, errors, _ = run(q(**base))
    assert any("unanswerable_reason" in m for m in errors)
    _, errors, _ = run(q(**base, unanswerable_reason="not_in_kb"))
    assert errors == []


def test_ambiguous_rules():
    amb = {"type": "ambiguous", "needs_clarification": True, "country": None, "critical_facts": []}
    _, errors, _ = run(q(**amb))
    assert errors == []
    _, errors, _ = run(q(**amb, query="How long is a refund in riyals?"))
    assert any("implies SA" in m for m in errors)
    _, errors, _ = run(q(type="ambiguous"))
    assert any("go together" in m for m in errors)


def test_country_signal_warnings():
    assert implied_countries("كم رسوم التحويل بالريال") == {"SA"}
    assert implied_countries("ابعت فلوس من القاهرة") == {"EG"}
    assert implied_countries("ابي ارجع فلوسي") == set()  # dialect alone implies nothing
    assert implied_countries("عملية غير مصرح بها") == set()  # مصرح isn't مصر
    assert implied_countries("حسابي بالسعودية") == {"SA"}
    assert implied_countries("سويت transfer بالدرهم") == {"AE"}
    assert implied_countries("بطاقة مصرية") == {"EG"}
    _, _, warnings = run(q(country=None, query="Refund time for a payment in Dubai?"))
    assert any("implies AE" in m for m in warnings)


def test_multi_hop_and_gold_source():
    res, errors, _ = run(
        q(type="multi_hop", gold_chunk_ids=["kb-0071#c0", "kb-0200#c0"], critical_facts=[])
    )
    assert errors == []
    assert res.queries[0].gold_source == "mixed"
    _, errors, _ = run(q(type="multi_hop"))
    assert any("2 or 3" in m for m in errors)


def test_parallel_group_must_agree():
    a = q(parallel_group="pg-001")
    b = q(qid="q-0002", query="ابي ارجع فلوسي", variety="gulf", parallel_group="pg-001")
    _, errors, warnings = run(a, b)
    assert errors == []
    assert any("missing varieties" in m for m in warnings)
    c = q(qid="q-0003", query="عايز فلوسي", variety="levantine_egyptian",
          parallel_group="pg-001", difficulty="hard", country="AE")  # fmt: skip
    _, errors, _ = run(a, b, c)
    assert any("differs" in m and "country" in m for m in errors)


def test_duplicates_and_unverified():
    _, errors, _ = run(q(), q())
    assert any("qid used by 2" in m for m in errors)
    _, _, warnings = run(q(verified=False))
    assert any("not verified" in m for m in warnings)


def test_search_finds_and_filters_by_country():
    hits = search(CHUNKS, "instapay", k=3)
    assert hits[0][1].chunk_id == "kb-0300#c0"
    assert search(CHUNKS, "instapay", k=3, country="SA") == []


def test_committed_eval_set_builds_and_outputs_are_current():
    res, outputs = build(ROOT)
    assert [str(e) for e in res.errors] == []
    for path, content in outputs.items():
        assert path.exists() and path.read_text(encoding="utf-8") == content, (
            f"{path.name} is stale: run `uv run python -m musaid.benchmark.build`"
        )


def test_competitor_check_flags_equivalent_chunks():
    from musaid.benchmark.review import competitors

    chunks = dict(CHUNKS)
    chunks["kb-0400#c0"] = chunk("kb-0400#c0", rewritten=False, title="Refunds FAQ")
    flagged = competitors(q(), chunks)
    assert [c.chunk_id for c in flagged] == ["kb-0400#c0"]
    assert competitors(q(gold_chunk_ids=["kb-0071#c0", "kb-0400#c0"]), chunks) == []
