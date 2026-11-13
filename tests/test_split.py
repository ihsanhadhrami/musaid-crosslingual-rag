"""Dev/test split and test-set lock."""

import hashlib
import json

from musaid.benchmark.build import ROOT
from musaid.benchmark.schema import Query
from musaid.benchmark.split import assign, make_lock, verify_lock

VARIETIES = ["english", "msa", "gulf", "levantine_egyptian", "code_switched", "arabizi"]


def mk(qid, variety="english", type_="factual", pg=None, gold_source="rewritten"):
    return Query(
        qid=qid, query="x", variety=variety, script="latin", type=type_, country=None,
        answerable=True, needs_clarification=False, unanswerable_reason=None,
        gold_chunk_ids=["kb-0001#c0"], gold_source=gold_source, reference_answer="x",
        critical_facts=[], parallel_group=pg, about_old_policy=False, difficulty="easy",
    )  # fmt: skip


def sample():
    qs, n = [], 0
    for g in range(10):
        for v in VARIETIES:
            n += 1
            qs.append(mk(f"q-{n:04d}", v, "number_sensitive", pg=f"pg-{g + 1:03d}"))
    for i in range(90):
        n += 1
        qs.append(mk(f"q-{n:04d}", VARIETIES[i % 6], ["factual", "procedural"][i % 2]))
    return qs


def test_exact_size_whole_groups_and_deterministic():
    qs = sample()
    a = assign(qs, {}, {}, test_size=90)
    assert sum(v == "test" for v in a.values()) == 90
    for g in {q.parallel_group for q in qs if q.parallel_group}:
        assert len({a[q.qid] for q in qs if q.parallel_group == g}) == 1
    assert assign(qs, {}, {}, test_size=90) == a


def test_existing_assignments_are_kept_and_ties_respected():
    qs = sample()
    first = assign(qs[:-10], {}, {}, test_size=80)
    second = assign(qs, first, {"q-0150": "q-0149"}, test_size=90)
    assert all(second[k] == v for k, v in first.items())
    assert second["q-0150"] == second["q-0149"]


def test_lock_detects_changed_test_file_and_chunks():
    test = [mk("q-0001")]
    content = json.dumps(test[0].model_dump(mode="json")) + "\n"
    hashes = {"kb-0001#c0": "abc"}
    lock = make_lock(content, test, hashes)
    assert lock["sha256"] == hashlib.sha256(content.encode()).hexdigest()
    assert verify_lock(lock, content, hashes) == []
    assert verify_lock(lock, content + " ", hashes)
    assert verify_lock(lock, content, {"kb-0001#c0": "changed"})


def test_committed_split_is_complete_and_sized():
    split = json.loads((ROOT / "data" / "eval" / "split.json").read_text(encoding="utf-8"))
    assert sum(v == "test" for v in split.values()) == 275
    test = (ROOT / "data" / "eval" / "test.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(test) == 275


def test_agreement_sample_and_scoring():
    from musaid.benchmark.agreement import cohen_kappa, draw_sample, score

    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert abs(cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"])) < 1e-9
    qs = sample()
    picked = draw_sample(qs)
    groups = [q.parallel_group for q in picked if q.parallel_group]
    assert len(groups) == len(set(groups))  # at most one per parallel group
    ours = {q.qid: q for q in qs}
    theirs = [
        {"qid": q.qid, "variety": q.variety, "type": q.type, "answerable": True,
         "needs_clarification": False, "gold_chunk_ids": q.gold_chunk_ids}
        for q in picked
    ]  # fmt: skip
    s = score(ours, theirs)
    assert s["gold"]["exact"] == 1.0 and s["disagreements"] == []
