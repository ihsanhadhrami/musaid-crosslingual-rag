"""The real KB in data/kb must always build cleanly, and committed outputs must be current."""

from musaid.ingest.build import ROOT, Paths, build


def test_kb_has_no_errors_and_outputs_are_current():
    paths = Paths(ROOT)
    result, chunks, outputs = build(paths)
    assert [str(e) for e in result.errors] == []
    assert chunks
    for key, content in outputs.items():
        path = paths.outputs[key]
        assert path.read_text(encoding="utf-8") == content, (
            f"{path.name} is stale: run `uv run python -m musaid.ingest.build`"
        )


def test_every_chunk_maps_to_an_article():
    result, chunks, _ = build(Paths(ROOT))
    doc_ids = {a.doc_id for a in result.articles}
    assert {c.doc_id for c in chunks} == doc_ids
    assert len({c.chunk_id for c in chunks}) == len(chunks)
