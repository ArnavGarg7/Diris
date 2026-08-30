"""Background document processing: extract text -> chunk -> embed -> extract.

Incremental (M13): on re-processing, only *changed* chunks are embedded and
extracted. Chunks are diffed by content hash — unchanged chunks keep their
embedding, entities, and relationships; removed chunks (and their vectors /
graph facts) are deleted; only added chunks do the expensive LLM/embedding work.

Runs as a FastAPI BackgroundTask. Never crashes the server: failures are caught
and recorded as a `failed` status.
"""
from __future__ import annotations

import logging

from ..db.repositories import (
    ChunkRepository,
    DocumentRepository,
    ProcessingStatusRepository,
    content_hash,
)
from ..db.session import SessionLocal
from ..ingestion import chunk_text_with_sections, load_document
from ..vectorstore import get_vector_store
from .language import detect_language

log = logging.getLogger("diris.processing")


def process_document(document_id: int, force: bool = False) -> None:
    """Extract, (incrementally) chunk/embed/extract, recording status as it goes.

    `force=True` rebuilds everything (used by the reprocess endpoint); otherwise
    unchanged content is skipped and only changed chunks are reprocessed.
    Opens its OWN session (the request session is already closed by task time).
    """
    with SessionLocal() as db:
        status_repo = ProcessingStatusRepository(db)
        document = DocumentRepository(db).get(document_id)
        if document is None:
            log.warning("process_document: document %s not found", document_id)
            return

        status_repo.record(document_id, "processing", stage="start")
        added_chunks = []
        reused = removed = 0
        try:
            text = load_document(document.stored_path)
            language = detect_language(text)
            doc_hash = content_hash(text)

            # Whole-document unchanged -> nothing to do.
            if not force and document.content_hash == doc_hash and document.status == "done":
                status_repo.record(document_id, "done", stage="unchanged", message="no changes detected")
                return

            sectioned = chunk_text_with_sections(text)
            new_items = [(i, t, s, content_hash(t)) for i, (t, s) in enumerate(sectioned)]
            new_hashes = {h for (_, _, _, h) in new_items}

            chunk_repo = ChunkRepository(db)
            existing = chunk_repo.list_for_document(document_id)
            if force:
                existing_by_hash: dict[str, object] = {}
                to_remove = existing
            else:
                existing_by_hash = {c.content_hash: c for c in existing if c.content_hash}
                to_remove = [c for c in existing if c.content_hash not in new_hashes]

            vector_store = get_vector_store()

            # Removed chunks: drop their vectors, then rows (cascade -> mentions/relationships).
            removed_ids = [c.id for c in to_remove]
            removed = len(removed_ids)
            if removed_ids:
                vector_store.delete_ids([str(i) for i in removed_ids])
                chunk_repo.delete_by_ids(removed_ids)

            # Reused chunks: keep them (just refresh position/section). Added: collect.
            add_items = []
            for (i, t, s, h) in new_items:
                match = existing_by_hash.get(h)
                if match is not None:
                    match.chunk_index = i
                    match.section = s
                    reused += 1
                else:
                    add_items.append((i, t, s))
            db.commit()  # persist reused position/section updates

            # Insert + embed ONLY the added chunks (the expensive part, minimised).
            added_chunks = chunk_repo.insert_chunks(document_id, add_items)
            if added_chunks:
                vector_store.upsert(
                    ids=[str(c.id) for c in added_chunks],
                    texts=[c.content for c in added_chunks],
                    metadatas=[
                        {"user_id": document.user_id, "document_id": document_id, "chunk_index": c.chunk_index}
                        for c in added_chunks
                    ],
                )

            DocumentRepository(db).set_metadata(document_id, "language", language)
            DocumentRepository(db).set_content_hash(document_id, doc_hash)
        except Exception as exc:  # noqa: BLE001 — a bad file must not crash the worker
            log.exception("Processing failed for document %s", document_id)
            db.rollback()
            status_repo.record(document_id, "failed", stage="processing", message=str(exc)[:500])
            return

        # Entity extraction on the ADDED chunks only (best-effort; also cleans
        # up entities orphaned by removed chunks).
        try:
            from .extraction import extract_document

            # Report live progress on the slow per-chunk extraction loop so the
            # UI shows movement instead of a frozen "processing" badge.
            def _progress(done: int, total: int) -> None:
                status_repo.record(
                    document_id, "processing", stage="extract",
                    message=f"extracting entities {done}/{total}",
                )

            counts = extract_document(
                db, document_id,
                only_chunk_ids=[c.id for c in added_chunks],
                progress=_progress,
            )
            status_repo.record(
                document_id, "done", stage="extract",
                message=(f"+{len(added_chunks)} added, {reused} reused, -{removed} removed; "
                         f"{counts['entities']} entities, {counts['relationships']} relationships"),
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("Entity extraction failed for document %s", document_id)
            db.rollback()
            status_repo.record(
                document_id, "done", stage="extract_failed",
                message=f"+{len(added_chunks)} added; extraction error: {str(exc)[:400]}",
            )

        # Re-project the (updated) graph from current MySQL state (best-effort).
        try:
            from .graph_projection import project_document

            project_document(db, document_id)
        except Exception:  # noqa: BLE001
            log.exception("Neo4j projection failed for document %s", document_id)
