"""Pydantic models for request bodies and responses (the API's data contract)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    # from_attributes lets FastAPI build this straight from a SQLAlchemy User object.
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DocumentOut(BaseModel):
    # Note: stored_path and user_id are deliberately NOT exposed (internal details).
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    content_type: str
    size_bytes: int
    status: str
    created_at: datetime


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chunk_index: int
    char_count: int
    content: str


class ProcessingStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    stage: str | None
    message: str | None
    created_at: datetime


class SearchResultOut(BaseModel):
    chunk_id: int
    document_id: int | None
    score: float
    content: str


class HybridResultOut(BaseModel):
    chunk_id: int
    document_id: int | None
    content: str
    score: float
    sources: list[str]  # which retrievers matched: vector / keyword / graph


class RelationshipOut(BaseModel):
    id: int
    source_entity_id: int
    target_entity_id: int
    type: str
    evidence: str | None
    confidence: float

    @classmethod
    def from_relationship(cls, rel) -> "RelationshipOut":
        return cls(
            id=rel.id,
            source_entity_id=rel.source_entity_id,
            target_entity_id=rel.target_entity_id,
            type=rel.type,
            evidence=rel.evidence,
            confidence=rel.confidence,
        )


class EntityOut(BaseModel):
    id: int
    canonical_name: str
    type: str
    description: str | None
    aliases: list[str]
    mention_count: int

    @classmethod
    def from_entity(cls, entity) -> "EntityOut":
        return cls(
            id=entity.id,
            canonical_name=entity.canonical_name,
            type=entity.type,
            description=entity.description,
            aliases=[a.alias for a in entity.aliases],
            mention_count=len(entity.mentions),
        )


class EntityDetailOut(EntityOut):
    relationships: list[RelationshipOut]

    @classmethod
    def from_entity_with_relationships(cls, entity, relationships) -> "EntityDetailOut":
        base = EntityOut.from_entity(entity)
        return cls(
            **base.model_dump(),
            relationships=[RelationshipOut.from_relationship(r) for r in relationships],
        )


class GraphNodeOut(BaseModel):
    entity_id: int
    name: str
    type: str


class GraphEdgeOut(BaseModel):
    source: int
    target: int
    type: str
    confidence: float | None


class NeighborhoodOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]


class GraphOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]


class PathOut(BaseModel):
    found: bool
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    # Optional: answer in this language (e.g. "Hindi"). Defaults to the question's language.
    answer_language: str | None = Field(default=None, max_length=40)
    # Optional: continue an existing conversation (enables multi-turn memory).
    conversation_id: int | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str
    created_at: datetime


class ConversationOut(BaseModel):
    id: int
    created_at: datetime
    message_count: int

    @classmethod
    def from_conversation(cls, conversation) -> "ConversationOut":
        return cls(
            id=conversation.id,
            created_at=conversation.created_at,
            message_count=len(conversation.messages),
        )


class ConversationDetailOut(BaseModel):
    id: int
    created_at: datetime
    messages: list[MessageOut]


class CitationOut(BaseModel):
    chunk_id: int
    document_id: int
    document_name: str
    section: str | None
    chunk_index: int
    snippet: str


class AnswerOut(BaseModel):
    answer: str
    answered: bool          # false = the documents don't contain the answer
    confidence: float
    citations: list[CitationOut]  # resolvable source references
    reasoning: str
    conversation_id: int | None = None  # set when the turn was part of a conversation
