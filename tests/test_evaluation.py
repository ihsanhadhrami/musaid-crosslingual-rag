"""Retrieval harness and the BM25 baseline on a toy corpus."""

from musaid.benchmark.schema import Query
from musaid.evaluation.harness import breakdown, metrics_for, per_query
from musaid.retrieval.bm25 import BM25Retriever

CHUNKS = [
    {"chunk_id": "kb-0001#c0", "text": "Refund timelines. Merchant refunds take 7 business days."},
    {"chunk_id": "kb-0002#c0", "text": "Card replacement fees. A lost card costs SAR 25."},
    {"chunk_id": "kb-0003#c0", "text": "Transfer limits. The daily transfer limit is SAR 20,000."},
]


def q(qid, text, gold, variety="english", pg=None):
    return Query(
        qid=qid, query=text, variety=variety, script="latin", type="factual", country=None,
        answerable=True, needs_clarification=False, unanswerable_reason=None,
        gold_chunk_ids=gold, gold_source="rewritten", reference_answer="x", critical_facts=[],
        parallel_group=pg, about_old_policy=False, difficulty="easy",
    )  # fmt: skip


def test_bm25_finds_the_right_chunk_and_arabic_gets_nothing():
    r = BM25Retriever(CHUNKS)
    en, ar = r.search(["how much to replace a lost card", "كم رسوم البطاقة"], k=3)
    assert next(iter(sorted(en, key=en.get, reverse=True))) == "kb-0002#c0"
    assert ar == {}


def test_metrics_and_breakdown():
    queries = [
        q("q-0001", "a", ["kb-0001#c0"], pg="pg-001"),
        q("q-0002", "b", ["kb-0002#c0"], variety="gulf", pg="pg-001"),
    ]
    rankings = {"q-0001": {"kb-0001#c0": 2.0, "kb-0003#c0": 1.0}, "q-0002": {}}
    m = metrics_for(queries, rankings)
    assert m["n"] == 2 and m["recall@10"] == 0.5 and m["mrr@10"] == 0.5
    pq = per_query(queries, rankings)
    assert pq["q-0001"]["first_gold_rank"] == 1 and pq["q-0002"]["first_gold_rank"] is None
    b = breakdown(queries, rankings)
    assert b["variety"]["gulf"]["recall@10"] == 0.0
    assert b["parallel_group_recall@10"]["pg-001"] == {"english": 1.0, "gulf": 0.0}


def test_dense_search_ranks_by_cosine_without_loading_a_model():
    import numpy as np

    from musaid.retrieval.dense import DenseRetriever

    class Stub:
        def encode(self, texts, **_):
            table = {"refund": [1.0, 0.0], "card": [0.0, 1.0]}
            return np.array([table[t] for t in texts], dtype=np.float32)

    r = DenseRetriever.__new__(DenseRetriever)
    r.ids, r.model, r.batch_size = ["kb-0001#c0", "kb-0002#c0"], Stub(), 8
    r.matrix = np.array([[0.9, 0.1], [0.1, 0.9]], dtype=np.float32)
    (hits,) = r.search(["card"], k=2)
    assert list(hits) == ["kb-0002#c0", "kb-0001#c0"]
