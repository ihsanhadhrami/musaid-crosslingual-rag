"""Dense multilingual retrieval (spec §4, ablation #2): one embedding space for Arabic
queries and English chunks.

Needs the optional `dense` dependency group: `uv sync --group dense`.
Chunk embeddings are cached in data/cache/ (gitignored), keyed by model and chunk text.
"""

import hashlib
import json
from pathlib import Path

import numpy as np


class DenseRetriever:
    def __init__(
        self,
        chunks: list[dict],
        model_name: str = "BAAI/bge-m3",
        cache_dir: Path | None = None,
        max_seq_length: int = 512,
        batch_size: int = 8,
    ):
        from sentence_transformers import SentenceTransformer

        self.ids = [c["chunk_id"] for c in chunks]
        self.model = SentenceTransformer(model_name, device="cpu")
        self.model.max_seq_length = max_seq_length
        self.batch_size = batch_size
        texts = [c["text"] for c in chunks]
        key = hashlib.sha1(
            json.dumps([model_name, max_seq_length, texts], ensure_ascii=False).encode()
        ).hexdigest()[:16]
        path = (
            cache_dir / f"chunks__{model_name.replace('/', '_')}__{key}.npy" if cache_dir else None
        )
        if path and path.exists():
            self.matrix = np.load(path)
        else:
            self.matrix = self._encode(texts, show_progress=True)
            if path:
                path.parent.mkdir(parents=True, exist_ok=True)
                np.save(path, self.matrix)

    def _encode(self, texts: list[str], show_progress: bool = False) -> np.ndarray:
        vecs = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=show_progress,
        )
        return vecs.astype(np.float32)

    def search(self, texts: list[str], k: int = 100) -> list[dict[str, float]]:
        q = self._encode(texts)
        sims = q @ self.matrix.T  # cosine, since both sides are normalized
        k = min(k, len(self.ids))
        out = []
        for row in sims:
            top = np.argpartition(-row, k - 1)[:k]
            top = top[np.argsort(-row[top])]
            out.append({self.ids[i]: float(row[i]) for i in top})
        return out
