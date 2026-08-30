"""Explainable question answering (FR-8, FR-9, FR-10, FR-11, FR-12).

Takes the hybrid evidence bundle and asks Claude to produce a cited answer
with a confidence score and a reasoning path, in the requested language.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..llm import BaseLLM, get_llm
from ..retrieval import Evidence

SYSTEM = (
    "You are an explainable question-answering assistant grounded in a document "
    "knowledge base. You answer ONLY from the provided evidence (text chunks and "
    "knowledge-graph facts). If the evidence is insufficient, say so plainly. "
    "Always cite the chunk ids you used. Never fabricate citations."
)

PROMPT_TEMPLATE = """Answer the user's question using ONLY the evidence below.

Answer in this language: {language}

=== KNOWLEDGE GRAPH FACTS ===
{graph_facts}

=== TEXT CHUNKS ===
{chunks}

=== CONVERSATION SO FAR ===
{history}

=== QUESTION ===
{question}

Return ONLY valid JSON, no prose, with this shape:
{{
  "answer": "your answer, citing chunks inline like [C1], [C3]",
  "citations": ["C1", "C3"],
  "reasoning_path": "1-3 sentences on how the evidence connects to the answer",
  "confidence": 0.0-1.0,
  "conflicts": "note any conflicting evidence with citations, or empty string"
}}

If the evidence does not contain the answer, set confidence low and say what is missing."""


@dataclass
class Answer:
    answer: str
    citations: list[str] = field(default_factory=list)
    reasoning_path: str = ""
    confidence: float = 0.0
    conflicts: str = ""
    sources: dict = field(default_factory=dict)  # C# -> {doc, chunk_id}


def _format_graph(evidence: Evidence) -> str:
    if not evidence.graph_edges:
        return "(no matching graph facts)"
    lines = []
    for e in evidence.graph_edges[:40]:
        src = evidence.graph_nodes.get(e["source"], {}).get("name", e["source"])
        tgt = evidence.graph_nodes.get(e["target"], {}).get("name", e["target"])
        lines.append(f"- {src} --[{e['type']}]--> {tgt}  (confidence {e['confidence']:.2f})")
    return "\n".join(lines)


def _format_chunks(evidence: Evidence, max_chunks: int = 8):
    labels, sources, lines = {}, {}, []
    for i, (chunk, score) in enumerate(evidence.chunks[:max_chunks], start=1):
        label = f"C{i}"
        labels[chunk.id] = label
        sources[label] = {"doc": chunk.doc, "chunk_id": chunk.id}
        lines.append(f"[{label}] (from {chunk.doc})\n{chunk.text.strip()}")
    return "\n\n".join(lines) if lines else "(no text chunks retrieved)", sources


def answer_question(
    question: str,
    evidence: Evidence,
    llm: BaseLLM | None = None,
    language: str = "the same language as the question",
    history: list[dict] | None = None,
) -> Answer:
    llm = llm or get_llm()
    chunks_text, sources = _format_chunks(evidence)
    history_text = _format_history(history)
    prompt = PROMPT_TEMPLATE.format(
        language=language,
        graph_facts=_format_graph(evidence),
        chunks=chunks_text,
        history=history_text,
        question=question,
    )
    data = llm.extract_json(prompt, system=SYSTEM)
    return Answer(
        answer=data.get("answer", ""),
        citations=data.get("citations", []),
        reasoning_path=data.get("reasoning_path", ""),
        confidence=float(data.get("confidence", 0.0) or 0.0),
        conflicts=data.get("conflicts", ""),
        sources=sources,
    )


def _format_history(history: list[dict] | None) -> str:
    if not history:
        return "(no prior turns)"
    return "\n".join(f"{t['role'].upper()}: {t['content']}" for t in history[-6:])
