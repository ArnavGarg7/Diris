# DIRIS — Data Injection and Retrieval System

A knowledge-graph-based document intelligence platform. Unlike plain RAG (which
relies only on vector similarity), DIRIS builds an **evolving knowledge graph**
from your documents and answers questions with **hybrid retrieval** — graph +
vector + keyword — producing **cited, explainable** answers.

This repository is an **MVP vertical slice** of the full [PRD](<Product Requirements Document - 2.docx>):
it implements the core loop end-to-end so it can be demoed and extended.

```
  ┌──────────┐   ┌─────────────┐   ┌───────────────┐   ┌──────────────┐   ┌─────────┐
  │  Ingest  │──▶│  Extract    │──▶│ Knowledge     │──▶│  Hybrid      │──▶│  Answer │
  │ pdf/docx │   │ entities +  │   │ Graph +       │   │  Retrieval   │   │ + cites │
  │ txt/html │   │ relations   │   │ Vector index  │   │ (KG+vec+kw)  │   │ + score │
  └──────────┘   └─────────────┘   └───────────────┘   └──────────────┘   └─────────┘
       FR-2/3         FR-4/5            FR-6/vector          FR-7           FR-8/12
```

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # then edit .env and paste your ANTHROPIC_API_KEY
```

```bash
python -m diris ingest data/documents            # build the knowledge base
python -m diris ask "Who walked on the Moon?"    # one-shot question
python -m diris chat                              # interactive, remembers context
python -m diris stats                             # knowledge base summary
```

A sample document (`data/documents/sample_knowledge.md`) is included so you can
run the full pipeline immediately.

## Development & tests

```bash
pip install -r requirements-dev.txt
pytest                     # offline suite — no API key needed
```

Conventions (branching, commit style, Definition of Done) are in
[CONTRIBUTING.md](CONTRIBUTING.md). The incremental build plan is in
[ROADMAP.md](ROADMAP.md).

## How it maps to the PRD

| PRD requirement | Where it lives |
|---|---|
| FR-2/3 Upload & processing | `diris/ingestion/` (loaders + chunker) |
| FR-4/5 Entity & relationship extraction | `diris/extraction/` (LLM-driven) |
| FR-6 Knowledge graph (merge, provenance, confidence) | `diris/graph/store.py` |
| FR-7 Hybrid retrieval | `diris/retrieval/hybrid.py` + `diris/vectorstore/` |
| FR-8/9 Question answering & cross-doc reasoning | `diris/qa/answer.py` |
| FR-10 Multilingual | answer language is a parameter in `qa/answer.py` |
| FR-11 Conversation memory | `chat` command keeps history |
| FR-12 Explainability | every answer returns citations, confidence, reasoning path |
| FR-14 Incremental updates | re-run `ingest`; stores merge, no rebuild |

## Architecture notes & deliberate MVP simplifications

The interfaces are designed so each piece can be upgraded independently
(FR: "replaceable graph database", "replaceable LLM backend"):

| Component | MVP implementation | Production upgrade path |
|---|---|---|
| Graph store | pure-Python dict + JSON | Neo4j / a graph DB behind the same `KnowledgeGraph` API |
| Vector search | TF-IDF over numpy | dense embeddings (Voyage / sentence-transformers) + FAISS/pgvector |
| Entity linking | case-insensitive name/alias match | embedding-based coreference & entity resolution |
| Ingestion | text/HTML/PDF/DOCX text | OCR, layout analysis, table/chart/equation extraction (FR-3) |
| LLM | Claude via `output_config.effort` | same, tune model per stage for cost |

### Known limitations (good next tasks)
- Entity matching is naive substring matching — "Armstrong" won't match the
  node "Neil Armstrong". Next: alias expansion + embedding similarity.
- Extraction runs one LLM call per chunk (sequential). Next: the Batch API or
  concurrency for large corpora.
- No auth / multi-tenant isolation yet (FR-1). Next: wrap in the FastAPI service.

## Configuration

All via `.env` (see `.env.example`): `ANTHROPIC_API_KEY`, `DIRIS_MODEL`
(default `claude-opus-5`; switch to `claude-sonnet-5` / `claude-haiku-4-5` for
cheaper bulk extraction), and `DIRIS_STORE_DIR`.
