"""LLM-driven knowledge extraction: entities + relationships from a chunk."""
from __future__ import annotations

from ..llm import BaseLLM, get_llm
from .schema import ENTITY_TYPES, RELATION_HINTS, Entity, Extraction, Relationship

SYSTEM = (
    "You are an information-extraction engine that builds knowledge graphs. "
    "You read a passage and return the entities and the semantic relationships "
    "between them. Be precise; do not invent facts that are not supported by "
    "the text. Prefer canonical entity names (e.g. 'Albert Einstein', not 'he')."
)

PROMPT_TEMPLATE = """Extract a knowledge graph from the passage below.

Entity types to use (pick the best fit; use CONCEPT if unsure):
{entity_types}

Relationship types are open-ended. Prefer these when they fit, otherwise
invent a concise snake_case type that captures the relation:
{relation_hints}

Return ONLY valid JSON with this exact shape, no prose:
{{
  "entities": [
    {{"name": "...", "type": "...", "description": "one short clause"}}
  ],
  "relationships": [
    {{"source": "...", "target": "...", "type": "...",
      "evidence": "short quote or paraphrase", "confidence": 0.0-1.0}}
  ]
}}

Rules:
- Every relationship's source and target MUST appear in "entities".
- Resolve pronouns to the entity they refer to.
- Omit trivia; keep the graph meaningful.
- If the passage has no meaningful entities, return {{"entities": [], "relationships": []}}.

PASSAGE:
\"\"\"
{passage}
\"\"\"
"""


def extract_knowledge(chunk: str, llm: BaseLLM | None = None) -> Extraction:
    llm = llm or get_llm()
    prompt = PROMPT_TEMPLATE.format(
        entity_types=", ".join(ENTITY_TYPES),
        relation_hints=", ".join(RELATION_HINTS),
        passage=chunk,
    )
    data = llm.extract_json(prompt, system=SYSTEM)
    return _coerce(data)


def _coerce(data) -> Extraction:
    """Validate loosely so one malformed row never sinks a whole chunk.

    Models sometimes return a bare list (of entities) instead of the expected
    object; be defensive about the top-level shape.
    """
    if isinstance(data, list):
        data = {"entities": data, "relationships": []}
    if not isinstance(data, dict):
        data = {}
    entities, rels = [], []
    for e in data.get("entities", []):
        try:
            entities.append(Entity(**e))
        except Exception:
            continue
    valid_names = {e.name for e in entities}
    for r in data.get("relationships", []):
        try:
            rel = Relationship(**r)
        except Exception:
            continue
        # Keep only edges whose endpoints were actually extracted.
        if rel.source in valid_names and rel.target in valid_names:
            rels.append(rel)
    return Extraction(entities=entities, relationships=rels)
