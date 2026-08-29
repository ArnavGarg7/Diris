"""End-to-end orchestration: ingestion -> extraction -> stores -> QA.

    from diris.pipeline import Pipeline
    p = Pipeline()
    p.ingest_path("data/documents/harry_potter.txt")
    ans = p.query("Who is Harry Potter?")
    print(ans.answer)
"""
from __future__ import annotations

from pathlib import Path

from .config import settings
from .extraction import extract_knowledge
from .graph import KnowledgeGraph
from .ingestion import chunk_text, load_document
from .ingestion.loaders import UnsupportedFormat
from .llm import BaseLLM, get_llm
from .qa import Answer, answer_question
from .retrieval import retrieve
from .vectorstore import Chunk, VectorStore

GRAPH_FILE = "graph.json"
VECTOR_FILE = "vectors.json"


class Pipeline:
    def __init__(self, store_dir: str | Path | None = None, llm: BaseLLM | None = None):
        self.store_dir = Path(store_dir or settings.store_dir)
        self.graph_path = self.store_dir / GRAPH_FILE
        self.vector_path = self.store_dir / VECTOR_FILE
        self.kg = KnowledgeGraph.load(self.graph_path)
        self.vs = VectorStore.load(self.vector_path)
        self._llm = llm  # lazily created so `stats` works without an API key

    @property
    def llm(self) -> BaseLLM:
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    # -- ingestion ---------------------------------------------------------
    def ingest_path(self, path: str | Path, verbose: bool = True) -> dict:
        path = Path(path)
        if path.is_dir():
            return self._ingest_dir(path, verbose)
        return self._ingest_file(path, verbose)

    def _ingest_dir(self, directory: Path, verbose: bool) -> dict:
        totals = {"documents": 0, "chunks": 0, "entities": 0, "relationships": 0}
        for file in sorted(directory.rglob("*")):
            if file.is_file():
                try:
                    res = self._ingest_file(file, verbose)
                except UnsupportedFormat as e:
                    if verbose:
                        print(f"  skip {file.name}: {e}")
                    continue
                for k in totals:
                    totals[k] += res.get(k, 0)
        return totals

    def _ingest_file(self, file: Path, verbose: bool) -> dict:
        text = load_document(file)
        chunks = chunk_text(text)
        doc = file.name
        n_ent = n_rel = 0
        if verbose:
            print(f"Ingesting {doc}: {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc}::{i}"
            self.vs.add(Chunk(id=chunk_id, doc=doc, text=chunk))
            try:
                extraction = extract_knowledge(chunk, llm=self.llm)
            except Exception as e:  # one bad chunk shouldn't abort the run
                if verbose:
                    print(f"  chunk {i}: extraction failed ({e})")
                continue
            for ent in extraction.entities:
                self.kg.add_entity(
                    ent.name, type=ent.type, description=ent.description,
                    chunk_id=chunk_id,
                )
                n_ent += 1
            for rel in extraction.relationships:
                self.kg.add_relationship(
                    rel.source, rel.target, type=rel.type,
                    evidence=rel.evidence, confidence=rel.confidence,
                    chunk_id=chunk_id,
                )
                n_rel += 1
            if verbose:
                print(f"  chunk {i}: +{len(extraction.entities)} entities, "
                      f"+{len(extraction.relationships)} relationships")
        self.save()
        return {"documents": 1, "chunks": len(chunks),
                "entities": n_ent, "relationships": n_rel}

    # -- query -------------------------------------------------------------
    def query(self, question: str, history: list[dict] | None = None,
              language: str = "the same language as the question") -> Answer:
        evidence = retrieve(question, self.vs, self.kg)
        return answer_question(question, evidence, llm=self.llm,
                               language=language, history=history)

    # -- misc --------------------------------------------------------------
    def stats(self) -> dict:
        s = self.kg.stats()
        s["chunks"] = len(self.vs.chunks)
        s["documents"] = len({c.doc for c in self.vs.chunks})
        return s

    def save(self) -> None:
        self.kg.save(self.graph_path)
        self.vs.save(self.vector_path)
