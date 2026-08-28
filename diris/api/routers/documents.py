"""Document library routes. All are scoped to the authenticated user."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from ...db.models import User
from ...db.repositories import ChunkRepository, ProcessingStatusRepository
from ...db.session import get_db
from ...services import documents as document_service
from ...services.processing import process_document
from ..deps import get_current_user
from ..schemas import ChunkOut, DocumentOut, ProcessingStatusOut

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentOut:
    doc = document_service.save_upload(db, current_user, file)
    # Process after the response is sent (extract -> chunk -> persist).
    background_tasks.add_task(process_document, doc.id)
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DocumentOut]:
    return document_service.list_documents(db, current_user)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentOut:
    return document_service.get_document(db, current_user, document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    document_service.delete_document(db, current_user, document_id)


@router.post("/{document_id}/reprocess", response_model=DocumentOut)
def reprocess_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentOut:
    doc = document_service.get_document(db, current_user, document_id)  # ownership check
    background_tasks.add_task(process_document, doc.id)
    return doc


@router.get("/{document_id}/status", response_model=list[ProcessingStatusOut])
def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProcessingStatusOut]:
    doc = document_service.get_document(db, current_user, document_id)
    return ProcessingStatusRepository(db).history_for_document(doc.id)


@router.get("/{document_id}/chunks", response_model=list[ChunkOut])
def get_document_chunks(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ChunkOut]:
    doc = document_service.get_document(db, current_user, document_id)
    return ChunkRepository(db).list_for_document(doc.id)
