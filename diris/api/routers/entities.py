"""Entity + relationship read endpoints (M6). All user-scoped."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ...db.models import User
from ...db.repositories import EntityRepository, RelationshipRepository
from ...db.session import get_db
from ...graph import get_graph_store
from ...services import documents as document_service
from ..deps import get_current_user
from ..schemas import (
    EntityDetailOut,
    EntityOut,
    GraphEdgeOut,
    GraphNodeOut,
    NeighborhoodOut,
)

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


@router.get("/entities/{entity_id}/neighborhood", response_model=NeighborhoodOut)
def entity_neighborhood(
    entity_id: int,
    hops: int = Query(1, ge=1, le=3),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NeighborhoodOut:
    # Ownership check first (404 for others' / missing entities).
    if EntityRepository(db).get_for_user(entity_id, current_user.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    try:
        sub = get_graph_store().neighborhood(current_user.id, entity_id, hops)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Graph store unavailable: {exc}",
        )
    if sub is None:  # entity not yet projected into the graph
        return NeighborhoodOut(nodes=[], edges=[])
    return NeighborhoodOut(
        nodes=[GraphNodeOut(**n) for n in sub["nodes"]],
        edges=[GraphEdgeOut(**e) for e in sub["edges"]],
    )
