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
from .language import detect_language, language_name, translate_to_english
from .retrieval import hybrid_search

_SNIPPET_CHARS = 300

QA_SYSTEM = (
    "You are a precise question-answering assistant grounded in a user's documents. "
    "Answer ONLY using the provided evidence (text chunks and knowledge-graph facts). "
    "Never use outside knowledge. If the evidence does not contain the answer, say so "
    "plainly and set answered=false. Cite the chunk numbers you relied on."
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
    # Detect the question's language; translate to English for retrieval so the
    # English-centric embedder + FULLTEXT still match English documents.
    lang = detect_language(question)
    retrieval_query = question if lang == "en" else translate_to_english(question)
    target_language = answer_language or language_name(lang)

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
    for i, r in enumerate(results, start=1):
        number_to_id[i] = r.chunk_id
        chunk_lines.append(f"[{i}] {r.content}")

    prompt = _build_prompt(question, chunk_lines, graph_facts, target_language)
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


def _graph_facts(db, user: User, question: str, max_facts: int = 20) -> list[str]:
    """Relationship facts around entities named in the question (enables multi-hop)."""
    try:
        seeds = get_entity_index().query(question, top_k=3, where={"user_id": user.id})
    except Exception:  # noqa: BLE001
        return []
    entity_repo = EntityRepository(db)
    rel_repo = RelationshipRepository(db)
    facts: list[str] = []
    seen: set[tuple] = set()
    for seed in seeds:
        for rel in rel_repo.for_entity(seed.chunk_id):  # entity index keys by entity id
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
    return facts


def _build_prompt(
    question: str, chunk_lines: list[str], graph_facts: list[str],
    answer_language: str = "English",
) -> str:
    facts_block = "\n".join(graph_facts) if graph_facts else "(none)"
    chunks_block = "\n\n".join(chunk_lines)
    return f"""Answer the question using ONLY the evidence below.

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
- Use ONLY the evidence above. Do NOT use outside knowledge.
- If the evidence does not contain the answer, set answered=false, keep confidence low,
  and say the documents don't cover it.
- Cite the [number] of every chunk you relied on."""
