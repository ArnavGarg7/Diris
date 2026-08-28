"""Entity + relationship read endpoints (M6). All user-scoped."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...db.models import User
from ...db.repositories import EntityRepository, RelationshipRepository
from ...db.session import get_db
from ...services import documents as document_service
from ..deps import get_current_user
from ..schemas import EntityDetailOut, EntityOut

router = APIRouter(tags=["entities"])


@router.get("/entities", response_model=list[EntityOut])
def list_entities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EntityOut]:
    entities = EntityRepository(db).list_for_user(current_user.id)
    return [EntityOut.from_entity(e) for e in entities]


@router.get("/entities/{entity_id}", response_model=EntityDetailOut)
def get_entity(
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EntityDetailOut:
    entity = EntityRepository(db).get_for_user(entity_id, current_user.id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    relationships = RelationshipRepository(db).for_entity(entity.id)
    return EntityDetailOut.from_entity_with_relationships(entity, relationships)


@router.get("/documents/{document_id}/entities", response_model=list[EntityOut])
def list_document_entities(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EntityOut]:
    document_service.get_document(db, current_user, document_id)  # ownership check (404)
    entities = EntityRepository(db).for_document(document_id, current_user.id)
    return [EntityOut.from_entity(e) for e in entities]
