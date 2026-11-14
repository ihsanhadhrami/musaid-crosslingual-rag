"""Lexical retrieval with bm25s over the English chunk text (spec §4, ablation #1)."""

import json
from pathlib import Path

import bm25s
import Stemmer


class BM25Retriever:
    """BM25 over each chunk's `text` (title, section path, countries, body).

    Queries go through the same English tokenizer and stemmer as the chunks. Arabic-script
    tokens never match an English index, which is exactly what the raw-query floor shows.
    """

    def __init__(self, chunks: list[dict], k1: float = 1.5, b: float = 0.75):
        self.ids = [c["chunk_id"] for c in chunks]
        self.stemmer = Stemmer.Stemmer("english")
        tokens = bm25s.tokenize(
            [c["text"] for c in chunks], stopwords="en", stemmer=self.stemmer, show_progress=False
        )
        self.index = bm25s.BM25(k1=k1, b=b)
        self.index.index(tokens, show_progress=False)

    def search(self, texts: list[str], k: int = 100) -> list[dict[str, float]]:
        tokens = bm25s.tokenize(texts, stopwords="en", stemmer=self.stemmer, show_progress=False)
        k = min(k, len(self.ids))
        docs, scores = self.index.retrieve(tokens, k=k, show_progress=False)
        out = []
        for row_docs, row_scores in zip(docs, scores, strict=True):
            hits = {self.ids[d]: float(s) for d, s in zip(row_docs, row_scores, strict=True)}
            out.append({cid: s for cid, s in hits.items() if s > 0})
        return out


def load_chunks(root: Path) -> list[dict]:
    path = root / "data" / "kb" / "chunks.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
