"""Background document processing: extract text -> chunk -> persist.

Runs as a FastAPI BackgroundTask after the upload response is sent. Drives the
status state machine (uploaded -> processing -> done | failed) and populates the
`chunks` table. Designed to never crash the server: any failure is caught and
recorded as a `failed` status with the error message.
"""
from __future__ import annotations

import logging

from ..db.repositories import (
    ChunkRepository,
    DocumentRepository,
    ProcessingStatusRepository,
)
from ..db.session import SessionLocal
from ..ingestion import chunk_text_with_sections, load_document
from ..vectorstore import get_vector_store
from .language import detect_language

log = logging.getLogger("diris.processing")


def process_document(document_id: int) -> None:
    """Extract, chunk, and persist a document, recording status as it goes.

    IMPORTANT: opens its OWN session. The request session that scheduled this
    task is already closed by the time the task runs.
    """
    with SessionLocal() as db:
        status_repo = ProcessingStatusRepository(db)
        document = DocumentRepository(db).get(document_id)
        if document is None:
            log.warning("process_document: document %s not found", document_id)
            return

        status_repo.record(document_id, "processing", stage="start")
        try:
            # --- extraction stage (OCR/layout would plug in behind load_document) ---
            text = load_document(document.stored_path)
            language = detect_language(text)

            # --- chunking stage (with section/heading provenance) ---
            sectioned = chunk_text_with_sections(text)
            chunks = [t for t, _ in sectioned]
            sections = [s for _, s in sectioned]

            # --- persist stage (idempotent: clear before re-adding) ---
            chunk_repo = ChunkRepository(db)
            chunk_repo.delete_for_document(document_id)
            saved_chunks = chunk_repo.add_chunks(document_id, chunks, sections=sections)
            DocumentRepository(db).set_metadata(document_id, "language", language)

            # --- embedding stage: store vectors in Chroma, keyed by chunk id ---
            vector_store = get_vector_store()
            vector_store.delete_document(document_id)  # idempotent re-embedding
            if saved_chunks:
                vector_store.upsert(
                    ids=[str(c.id) for c in saved_chunks],
                    texts=[c.content for c in saved_chunks],
                    metadatas=[
                        {
                            "user_id": document.user_id,
                            "document_id": document_id,
                            "chunk_index": c.chunk_index,
                        }
                        for c in saved_chunks
                    ],
                )

        except Exception as exc:  # noqa: BLE001 — a bad file must not crash the worker
            log.exception("Processing failed for document %s", document_id)
            db.rollback()  # clear the failed transaction so we can record status
            status_repo.record(
                document_id, "failed", stage="processing", message=str(exc)[:500]
            )
            return

        # Core succeeded: the document is chunked + searchable. Entity extraction
        # is best-effort enrichment — its failure (e.g. no API key) must NOT mark
        # the document failed, since chunks/embeddings are already usable.
        try:
            from .extraction import extract_document

            counts = extract_document(db, document_id)
            status_repo.record(
                document_id, "done", stage="extract",
                message=f"{len(chunks)} chunks, {counts['entities']} entities, "
                f"{counts['relationships']} relationships",
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("Entity extraction failed for document %s", document_id)
            db.rollback()
            status_repo.record(
                document_id, "done", stage="extract_failed",
                message=f"{len(chunks)} chunks; extraction error: {str(exc)[:400]}",
            )

        # Best-effort: project the resolved graph into Neo4j. Failure here (e.g.
        # Neo4j down) is logged but does not change the document's status.
        try:
            from .graph_projection import project_document

            project_document(db, document_id)
        except Exception:  # noqa: BLE001
            log.exception("Neo4j projection failed for document %s", document_id)
