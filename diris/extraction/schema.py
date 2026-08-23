"""Typed schema for what the LLM extracts from a chunk (FR-4, FR-5)."""
from __future__ import annotations

from pydantic import BaseModel, Field

# A non-exhaustive palette to steer the model. It may invent new relation
# types from context (FR-5 explicitly allows this), so this is guidance only.
ENTITY_TYPES = [
    "PERSON", "ORGANIZATION", "LOCATION", "DATE", "EVENT",
    "CONCEPT", "TECHNOLOGY", "OBJECT", "TOPIC", "WORK",
]
RELATION_HINTS = [
    "belongs_to", "located_in", "works_for", "authored_by", "part_of",
    "depends_on", "causes", "affects", "treats", "references", "related_to",
]


class Entity(BaseModel):
    name: str
    type: str = "CONCEPT"
    description: str = ""


class Relationship(BaseModel):
    source: str                       # entity name
    target: str                       # entity name
    type: str = "related_to"
    evidence: str = ""                # short span justifying the edge
    confidence: float = Field(0.7, ge=0.0, le=1.0)


class Extraction(BaseModel):
    entities: list[Entity] = []
    relationships: list[Relationship] = []
