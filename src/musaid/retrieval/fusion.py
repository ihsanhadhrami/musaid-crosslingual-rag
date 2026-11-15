"""Reciprocal Rank Fusion (Cormack et al., 2009), the spec's fusion method (§4).

Each route contributes 1 / (k + rank) for every document it returns; scores are summed.
Only ranks matter, so BM25 and cosine scores never need to be put on one scale.
"""


def rrf(runs: list[dict[str, float]], k: int = 60, depth: int = 100) -> dict[str, float]:
    """Fuse ranked lists ({doc_id: score}, any score scale) into one, best first.

    `depth` limits how many documents of each input list count, and the length of the output.
    Ties are broken by doc id so the output is deterministic.
    """
    fused: dict[str, float] = {}
    for run in runs:
        ranked = sorted(run.items(), key=lambda kv: (-kv[1], kv[0]))[:depth]
        for rank, (doc, _) in enumerate(ranked, start=1):
            fused[doc] = fused.get(doc, 0.0) + 1.0 / (k + rank)
    top = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))[:depth]
    return dict(top)
