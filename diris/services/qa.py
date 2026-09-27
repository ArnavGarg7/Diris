"""Grounded question answering (M9).

Retrieve hybrid evidence (M8) + graph facts (M7), hand them to the LLM with
strict grounding instructions, and return a structured, cited answer that
admits when the documents don't contain the answer.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..db.models import Chunk, Document, User
from ..db.repositories import EntityRepository, RelationshipRepository
from ..llm import get_llm
from ..vectorstore import get_entity_index
from .persona import persona
from .retrieval import hybrid_search

_SNIPPET_CHARS = 300

QA_SYSTEM = persona() + (
    "\n\nRIGHT NOW you are answering a question from the user's documents and knowledge graph. "
    "Synthesize your answer using the provided evidence (text chunks and knowledge-graph facts). "
    "Use your analytical intelligence to interpret, compare, identify main characters, summarize themes, "
    "and analyze tone or style from the writing and events in the evidence. "
    "Stay faithful to the documents and do not invent fabricated facts, but DO synthesize, "
    "explain, and answer naturally. If the sources disagree, present BOTH viewpoints "
    "with their citations instead of choosing one. Cite the chunk numbers you relied on."
)


@dataclass
class Citation:
    chunk_id: int
    document_id: int
    document_name: str
    section: str | None
    chunk_index: int
    snippet: str


@dataclass
class Answer:
    answer: str
    answered: bool          # was the evidence sufficient to answer?
    confidence: float
    citations: list[Citation]   # resolvable source references
    reasoning: str


def answer_question(
    db, user: User, question: str, top_k: int = 6, answer_language: str | None = None
) -> Answer:
    """Single-turn entrypoint: route (small talk vs document question) then answer."""
    from .conversation import respond

    return respond(db, user, question, history="", answer_language=answer_language, top_k=top_k)


def answer_grounded(
    db, user: User, retrieval_query: str, user_message: str,
    answer_language: str | None = None, top_k: int = 6,
) -> Answer:
    """Grounded, cited answer. `retrieval_query` (English) drives retrieval;
    `user_message` (original) drives the answer language."""
    results = hybrid_search(db, user, retrieval_query, top_k=top_k)
    if not results:
        return Answer(
            answer="I couldn't find anything in your documents about that.",
            answered=False, confidence=0.0, citations=[],
            reasoning="No relevant evidence was retrieved.",
        )

    graph_facts = _graph_facts(db, user, retrieval_query)

    # Number the chunks so the model can cite them; map numbers back to ids.
    number_to_id: dict[int, int] = {}
    chunk_lines: list[str] = []
    doc_cache: dict[int, str] = {}
    for i, r in enumerate(results, start=1):
        number_to_id[i] = r.chunk_id
        doc_name = ""
        if r.document_id:
            if r.document_id not in doc_cache:
                doc = db.get(Document, r.document_id)
                doc_cache[r.document_id] = doc.original_filename if doc else ""
            doc_name = doc_cache[r.document_id]
        doc_header = f"[{i}] (Document: {doc_name})" if doc_name else f"[{i}]"
        chunk_lines.append(f"{doc_header}\n{r.content}")

    directive = answer_language or "the same language as the QUESTION above"
    prompt = _build_prompt(user_message, chunk_lines, graph_facts, directive)
    data = get_llm().extract_json(prompt, system=QA_SYSTEM)

    # Keep only cited numbers that were actually shown (no fabricated citations),
    # then resolve each to a rich, user-inspectable source reference.
    cited_ids = [
        number_to_id[n]
        for n in (data.get("citations") or [])
        if isinstance(n, int) and n in number_to_id
    ]
    result_by_id = {r.chunk_id: r for r in results}
    citations = [_build_citation(db, cid, result_by_id) for cid in cited_ids]
    citations = [c for c in citations if c is not None]

    return Answer(
        answer=str(data.get("answer", "")).strip(),
        answered=bool(data.get("answered", True)),
        confidence=float(data.get("confidence", 0.0) or 0.0),
        citations=citations,
        reasoning=str(data.get("reasoning", "")).strip(),
    )


def _build_citation(db, chunk_id: int, result_by_id) -> Citation | None:
    chunk = db.get(Chunk, chunk_id)
    if chunk is None:
        return None
    document = db.get(Document, chunk.document_id)
    content = result_by_id[chunk_id].content if chunk_id in result_by_id else chunk.content
    return Citation(
        chunk_id=chunk_id,
        document_id=chunk.document_id,
        document_name=document.original_filename if document else "",
        section=chunk.section,
        chunk_index=chunk.chunk_index,
        snippet=content.strip()[:_SNIPPET_CHARS],
    )


def _graph_facts(db, user: User, question: str, max_facts: int = 25) -> list[str]:
    """Relationship facts around entities named in the question (enables multi-hop).
    Also includes prominent entities and relationships across the user's documents
    so global/character/comparative questions are grounded with high-level context."""
    from sqlalchemy import func, select
    from ..db.models import Entity, EntityMention, Relationship

    facts: list[str] = []
    seen: set[tuple] = set()
    entity_repo = EntityRepository(db)
    rel_repo = RelationshipRepository(db)

    # 1. Include prominent figures/entities for each user document
    try:
        user_docs = db.execute(select(Document).where(Document.user_id == user.id)).scalars().all()
        for doc in user_docs:
            top_ents = db.execute(
                select(Entity.canonical_name, Entity.type, func.count(EntityMention.id).label("cnt"))
                .join(EntityMention, EntityMention.entity_id == Entity.id)
                .where(EntityMention.document_id == doc.id)
                .group_by(Entity.id)
                .order_by(func.count(EntityMention.id).desc())
                .limit(7)
            ).all()
            if top_ents:
                ent_desc = ", ".join(f"{name} ({t}, {cnt} mentions)" for name, t, cnt in top_ents)
                facts.append(f"Document '{doc.original_filename}': Prominent entities: {ent_desc}")
    except Exception:  # noqa: BLE001
        pass

    # 2. Targeted entity facts based on query seeds
    try:
        seeds = get_entity_index().query(question, top_k=5, where={"user_id": user.id})
    except Exception:  # noqa: BLE001
        seeds = []

    seed_ids = [s.chunk_id for s in seeds]
    for eid in seed_ids:
        for rel in rel_repo.for_entity(eid):
            key = (rel.source_entity_id, rel.type, rel.target_entity_id)
            if key in seen:
                continue
            seen.add(key)
            src = entity_repo.get(rel.source_entity_id)
            tgt = entity_repo.get(rel.target_entity_id)
            if src and tgt:
                facts.append(f"{src.canonical_name} --{rel.type}--> {tgt.canonical_name}")
            if len(facts) >= max_facts:
                return facts

    # 3. High-confidence relationships across user's entities if facts are sparse
    if len(facts) < max_facts:
        try:
            top_rels = db.execute(
                select(Relationship)
                .where(Relationship.user_id == user.id)
                .order_by(Relationship.confidence.desc())
                .limit(max_facts - len(facts))
            ).scalars().all()
            for rel in top_rels:
                key = (rel.source_entity_id, rel.type, rel.target_entity_id)
                if key in seen:
                    continue
                seen.add(key)
                src = entity_repo.get(rel.source_entity_id)
                tgt = entity_repo.get(rel.target_entity_id)
                if src and tgt:
                    facts.append(f"{src.canonical_name} --{rel.type}--> {tgt.canonical_name}")
                if len(facts) >= max_facts:
                    break
        except Exception:  # noqa: BLE001
            pass

    return facts


def _build_prompt(
    question: str, chunk_lines: list[str], graph_facts: list[str],
    answer_language: str = "English",
) -> str:
    facts_block = "\n".join(graph_facts) if graph_facts else "(none)"
    chunks_block = "\n\n".join(chunk_lines)
    return f"""Answer the question using the evidence below (text chunks and knowledge-graph facts).

Write the "answer" field in {answer_language}. The evidence and citations stay
in their original language.

KNOWLEDGE GRAPH FACTS:
{facts_block}

TEXT CHUNKS:
{chunks_block}

QUESTION: {question}

Return ONLY a JSON object of this exact shape:
{{
  "answer": "your answer, or a statement that the documents don't cover it",
  "answered": true or false,
  "confidence": 0.0 to 1.0,
  "citations": [chunk numbers you used, e.g. 1, 3],
  "reasoning": "one or two sentences on how the evidence supports the answer"
}}

Rules:
- Synthesize your answer intelligently from the evidence and knowledge-graph facts above.
- If the question asks about characters or people, identify the main and prominent figures, their roles, and connections from the facts and text.
- If the question asks about tone, style, atmosphere, or comparing documents, analyze the writing style, genre, setting, and mood shown in each document's chunks.
- Use your analytical intelligence to explain and summarize. Do not invent fabricated facts, but do not artificially refuse when the evidence gives you clear context.
- Only if the evidence truly provides zero relevant context or connection to the topic, state that the documents do not cover it and set answered=false.
- If two sources CONTRADICT each other, present BOTH conflicting facts in the answer, each attributed to its own [chunk number].
- Cite the [number] of every chunk you relied on in the "citations" array."""
