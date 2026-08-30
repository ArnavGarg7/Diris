"""Document library business logic: validate, store bytes, record metadata.

Security-critical choices live here:
  * the client filename is NEVER used as a storage path (path-traversal defense)
  * uploads are validated against an extension allowlist and a size cap
  * files are written under a per-user directory; the DB row is the source of truth
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..config import settings
from ..db.models import Document, User
from ..db.repositories import DocumentRepository


def validate_upload(filename: str, size_bytes: int) -> str:
    """Return the normalized extension, or raise HTTPException on rejection.

    Pure/parameterized so it is unit-testable without touching disk or the DB.
    """
    # Path(...).name strips any directory components a malicious client sent.
    ext = Path(Path(filename).name).suffix.lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext or '(none)'}'. "
            f"Allowed: {sorted(settings.allowed_extensions)}",
        )
    if size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file"
        )
    if size_bytes > settings.max_upload_mb * 1024 * 1024:
        # 413 Payload/Content Too Large (numeric literal avoids a Starlette
        # constant that was renamed across versions).
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {settings.max_upload_mb} MB)",
        )
    return ext


def save_upload(db: Session, user: User, upload: UploadFile) -> Document:
    original = Path(upload.filename or "unnamed").name  # display name, sanitized
    content = upload.file.read()
    ext = validate_upload(original, len(content))

    user_dir = settings.upload_dir / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    stored_path = user_dir / f"{uuid4().hex}{ext}"  # our own name, never the client's
    stored_path.write_bytes(content)

    try:
        return DocumentRepository(db).create(
            user_id=user.id,
            original_filename=original,
            stored_path=str(stored_path),
            content_type=upload.content_type or "application/octet-stream",
            size_bytes=len(content),
            metadata={"extension": ext},
        )
    except Exception:
        # Don't leave an orphan file on disk if the DB insert fails.
        stored_path.unlink(missing_ok=True)
        raise


def replace_document_content(
    db: Session, user: User, document_id: int, upload: UploadFile
) -> Document:
    """Replace an existing document's file content (triggers incremental reprocess)."""
    doc = get_document(db, user, document_id)  # ownership check (404)
    original = Path(upload.filename or "unnamed").name
    content = upload.file.read()
    ext = validate_upload(original, len(content))

    user_dir = settings.upload_dir / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    new_path = user_dir / f"{uuid4().hex}{ext}"
    new_path.write_bytes(content)

    old_path = doc.stored_path
    doc.original_filename = original
    doc.stored_path = str(new_path)
    doc.content_type = upload.content_type or "application/octet-stream"
    doc.size_bytes = len(content)
    doc.status = "uploaded"
    db.commit()
    db.refresh(doc)

    if old_path and old_path != str(new_path):
        Path(old_path).unlink(missing_ok=True)
    return doc


def list_documents(db: Session, user: User) -> list[Document]:
    return DocumentRepository(db).list_for_user(user.id)


def get_document(db: Session, user: User, document_id: int) -> Document:
    doc = DocumentRepository(db).get_for_user(document_id, user.id)
    if doc is None:
        # 404 (not 403) so we don't reveal that someone else's id exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return doc


def delete_document(db: Session, user: User, document_id: int) -> None:
    doc = get_document(db, user, document_id)
    Path(doc.stored_path).unlink(missing_ok=True)  # remove the file...
    _delete_vectors(document_id)                    # ...its vectors...
    DocumentRepository(db).delete(doc)              # ...then the DB rows (cascade)


def _delete_vectors(document_id: int) -> None:
    # Best-effort: a vector-store hiccup shouldn't block deleting the document.
    try:
        from ..vectorstore import get_vector_store

        get_vector_store().delete_document(document_id)
    except Exception:  # noqa: BLE001
        pass
