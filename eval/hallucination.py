"""Hallucination-resistance eval: refusal rate on out-of-scope questions.

Seeds an in-domain corpus (space facts), then asks questions whose answers are
NOT in the corpus. A well-grounded system should refuse (answered=false) rather
than invent an answer. This one calls the real LLM, so run it explicitly:

    python -m eval.hallucination
"""
from __future__ import annotations

import tempfile

from sqlalchemy import delete

from diris.db.models import User
from diris.db.repositories import ChunkRepository, DocumentRepository, UserRepository
from diris.db.session import SessionLocal
from diris.security import hash_password
from diris.services.qa import answer_question
from diris.vectorstore import get_vector_store, set_entity_index, set_vector_store
from diris.vectorstore.chroma_store import ChromaVectorStore

from .dataset import CHUNKS, OUT_OF_SCOPE

_EMAIL = "halluceval@diris.local"


def run() -> dict:
    tmp = tempfile.mkdtemp()
    set_vector_store(ChromaVectorStore(persist_dir=tmp + "/c", collection_name="h_chunks"))
    set_entity_index(ChromaVectorStore(persist_dir=tmp + "/e", collection_name="h_entities"))

    with SessionLocal() as db:
        db.execute(delete(User).where(User.email == _EMAIL))
        db.commit()
        user = UserRepository(db).create(_EMAIL, hash_password("evalpass123"))
        doc = DocumentRepository(db).create(
            user_id=user.id, original_filename="space.txt", stored_path="/x",
            content_type="text/plain", size_bytes=1,
        )
        chunks = ChunkRepository(db).add_chunks(doc.id, CHUNKS)
        get_vector_store().upsert(
            ids=[str(c.id) for c in chunks], texts=[c.content for c in chunks],
            metadatas=[{"user_id": user.id, "document_id": doc.id, "chunk_index": c.chunk_index} for c in chunks],
        )

        refused = 0
        for q in OUT_OF_SCOPE:
            ans = answer_question(db, user, q)
            print(f"Q: {q}\n   answered={ans.answered} -> {ans.answer[:80]}")
            if not ans.answered:
                refused += 1

        db.execute(delete(User).where(User.id == user.id))
        db.commit()

    return {"out_of_scope": len(OUT_OF_SCOPE), "refused": refused,
            "refusal_rate": round(refused / len(OUT_OF_SCOPE), 3)}


if __name__ == "__main__":  # pragma: no cover
    print(run())
