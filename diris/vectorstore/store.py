"""A small TF-IDF vector store (FR-7 vector similarity search).

Deliberately dependency-light: no embedding API key, no external DB. It gives
real lexical-semantic ranking with cosine similarity over TF-IDF vectors and
persists to JSON. The `search` interface is what a swap to dense embeddings
(Voyage, sentence-transformers) or a real vector DB would re-implement later.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class Chunk:
    id: str
    doc: str
    text: str
    meta: dict = field(default_factory=dict)


class VectorStore:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self._df: dict[str, int] = {}            # document frequency per term
        self._vectors: list[dict[str, float]] = []  # tf-idf per chunk
        self._norms: list[float] = []
        self._dirty = True

    def add(self, chunk: Chunk) -> None:
        self.chunks.append(chunk)
        for term in set(tokenize(chunk.text)):
            self._df[term] = self._df.get(term, 0) + 1
        self._dirty = True

    # -- indexing ----------------------------------------------------------
    def _idf(self, term: str) -> float:
        n = len(self.chunks)
        df = self._df.get(term, 0)
        return math.log((1 + n) / (1 + df)) + 1.0

    def _build(self) -> None:
        self._vectors, self._norms = [], []
        for chunk in self.chunks:
            tokens = tokenize(chunk.text)
            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            vec = {t: (c / len(tokens)) * self._idf(t) for t, c in tf.items()} if tokens else {}
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            self._vectors.append(vec)
            self._norms.append(norm)
        self._dirty = False

    # -- query -------------------------------------------------------------
    def search(self, query: str, top_k: int = 6) -> list[tuple[Chunk, float]]:
        if not self.chunks:
            return []
        if self._dirty:
            self._build()
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        q_tf: dict[str, int] = {}
        for t in q_tokens:
            q_tf[t] = q_tf.get(t, 0) + 1
        q_vec = {t: (c / len(q_tokens)) * self._idf(t) for t, c in q_tf.items()}
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        scored = []
        for chunk, vec, norm in zip(self.chunks, self._vectors, self._norms):
            dot = sum(q_vec.get(t, 0.0) * w for t, w in vec.items())
            if dot > 0:
                scored.append((chunk, dot / (q_norm * norm)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def get(self, chunk_id: str) -> Chunk | None:
        return next((c for c in self.chunks if c.id == chunk_id), None)

    # -- persistence -------------------------------------------------------
    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "df": self._df,
            "chunks": [
                {"id": c.id, "doc": c.doc, "text": c.text, "meta": c.meta}
                for c in self.chunks
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "VectorStore":
        store = cls()
        path = Path(path)
        if not path.exists():
            return store
        payload = json.loads(path.read_text(encoding="utf-8"))
        store._df = payload.get("df", {})
        store.chunks = [
            Chunk(id=c["id"], doc=c["doc"], text=c["text"], meta=c.get("meta", {}))
            for c in payload.get("chunks", [])
        ]
        store._dirty = True
        return store
