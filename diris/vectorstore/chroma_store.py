"""ChromaDB implementation of the vector store (Milestone 5).

Uses Chroma's built-in default embedding function (a local ONNX MiniLM model,
384-dim, no API key). Vectors are keyed by the MySQL chunk id and carry
{user_id, document_id, chunk_index} metadata for per-user filtering.
"""
from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import settings
from .base import VectorMatch, VectorStoreBase


class ChromaVectorStore(VectorStoreBase):
    def __init__(self, persist_dir: str | None = None, collection_name: str | None = None):
        self.client = chromadb.PersistentClient(
            path=str(persist_dir or settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        # cosine space -> distance in [0, 2]; we convert to a similarity score.
        self.collection = self.client.get_or_create_collection(
            name=collection_name or settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, ids: list[str], texts: list[str], metadatas: list[dict]) -> None:
        if not ids:
            return
        self.collection.upsert(ids=ids, documents=texts, metadatas=metadatas)

    @staticmethod
    def _build_where(where: dict | None) -> dict | None:
        # Chroma requires a single top-level operator; multiple fields must be
        # combined with $and (e.g. {"$and": [{"user_id": 1}, {"type": "X"}]}).
        if not where:
            return None
        if len(where) == 1:
            return where
        return {"$and": [{k: v} for k, v in where.items()]}

    def query(self, text: str, top_k: int, where: dict | None = None) -> list[VectorMatch]:
        result = self.collection.query(
            query_texts=[text], n_results=top_k, where=self._build_where(where)
        )
        # Chroma returns lists-of-lists (one row per query text); we sent one query.
        ids = result["ids"][0]
        docs = result["documents"][0]
        metas = result["metadatas"][0]
        dists = result["distances"][0]

        matches: list[VectorMatch] = []
        for cid, doc, meta, dist in zip(ids, docs, metas, dists):
            matches.append(
                VectorMatch(
                    chunk_id=int(cid),
                    document_id=meta.get("document_id"),
                    score=1.0 - float(dist),  # cosine distance -> similarity
                    text=doc,
                    metadata=meta,
                )
            )
        return matches

    def delete_document(self, document_id: int) -> None:
        self.collection.delete(where={"document_id": document_id})

    def delete_ids(self, ids: list[str]) -> None:
        if ids:
            self.collection.delete(ids=ids)

    def count(self) -> int:
        return self.collection.count()
