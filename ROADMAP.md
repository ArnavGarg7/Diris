# DIRIS — Implementation Roadmap

**Status:** Planning document. No milestone is implemented beyond the initial MVP vertical slice.
**Rule:** Work proceeds strictly milestone-by-milestone. Do not start a milestone until explicitly told "Start Milestone X."

---

## Working Protocol (applies to EVERY milestone)

Before any code is written for a milestone, we pass through a **Learn → Explain Back → Implement** checkpoint. This exists so the intern understands the system, not just ships it.

1. **Learn (Claude explains):** Claude explains the milestone's objective, architecture, the specific concepts it introduces, the files that will change, and *why*. Scoped to only what this milestone needs.
2. **Explain Back (intern confirms):** the intern explains the key concepts back in their own words and asks questions. **Claude does not start implementing until this happens.** If the explain-back reveals a gap, Claude re-explains before proceeding.
3. **Implement:** only after the checkpoint — Claude implements *only* this milestone (no future work), following the code-quality and AI/LLM rules.
4. **Test:** run unit/integration/smoke tests + edge cases; report exactly what was tested and the result.
5. **Explain code changes:** Claude walks through the code that was written for this milestone — file by file / component by component — what each piece does, how data flows through it, and the key design decisions. This is a teaching step so the intern can explain the implementation themselves.
6. **Review:** what changed, why, files, new deps, DB/API changes, tests, known limitations, security concerns, technical debt, what to learn, what's next.

Then: finish, test, **commit**, understand — and only then move to the next milestone. Never build ahead. The system must work after every milestone.

---

## A. Current Repository Audit

### A.1 What exists (1,069 LOC Python, one package `diris/`)

```
diris/
  config.py            settings from .env (api_key, model, store_dir, chunk/retrieval params)
  llm.py               Anthropic client wrapper: complete() + extract_json() with defensive JSON parse
  ingestion/
    loaders.py         txt/md/html built-in; pdf(pypdf)/docx(python-docx) optional, graceful degradation
    chunker.py         paragraph-aware sliding-window chunking with overlap
  extraction/
    schema.py          Pydantic: Entity, Relationship, Extraction; entity-type palette + relation hints
    extractor.py       LLM prompt -> entities+relationships; loose validation, drops bad rows
  graph/
    store.py           pure-Python KnowledgeGraph: node/edge dicts, merge-by-normalized-name,
                       provenance (chunk mentions), confidence accumulation, neighborhood(), JSON save/load
  vectorstore/
    store.py           TF-IDF VectorStore over numpy: add/search(cosine)/get, JSON save/load
  retrieval/
    hybrid.py          fuses vector hits + graph neighborhood + provenance chunks -> Evidence bundle
  qa/
    answer.py          evidence -> LLM -> Answer(answer, citations, reasoning_path, confidence, conflicts)
  pipeline.py          orchestration: ingest_path(), query(), stats(), save()
  cli.py / __main__.py argparse CLI: ingest / ask / chat / stats
data/documents/sample_knowledge.md   sample corpus
data/store/                          (empty) JSON persistence target
README.md, requirements.txt, .env.example, PRD (.docx)
```

### A.2 Engineering quality assessment (critical, not celebratory)

**Genuinely good (keep the discipline):**
- Clean module cohesion; each concern isolated. LLM access is already behind one interface (`llm.py`).
- Two real abstractions exist: `KnowledgeGraph` and `VectorStore` — both have a small, swappable surface.
- Provenance is tracked end-to-end (chunk → entity/edge → citation). This is the hardest thing to retrofit later, and it's already there.
- Config externalized; **no hardcoded secrets**; graceful loader degradation; defensive JSON parsing.

**Weak / risky / missing (the honest list):**
1. **No Git repository.** Directly violates the mentor's "Git from Day 1" mandate. Highest-priority fix.
2. **No committed tests.** Only ad-hoc smoke tests run in a shell; nothing reproducible in the repo. No `tests/`, no CI.
3. **No `.gitignore`.** `.env`, `data/store/*.json`, `__pycache__/`, and the venv would all get committed by accident.
4. **Naive entity resolution.** `find_entities` and merge use case-insensitive substring/exact-name matching. "Armstrong" ≠ "Neil Armstrong". This is a correctness ceiling, not a polish item.
5. **Sequential, one-LLM-call-per-chunk extraction.** No batching, no concurrency, no caching → slow and costly on real corpora.
6. **Toy persistence.** Whole graph + vector index live in memory and serialize to a single JSON file each. Not concurrent-safe, O(N) full rebuilds, no query engine. Fine for a demo; wrong for the target system.
7. **No API, no auth, no multi-user isolation.** Single global store. FR-1 (users/libraries) is entirely absent.
8. **No observability / cost tracking.** No logging of LLM token usage, failures, or timings.
9. **Confidence is a heuristic** (`+0.05` per re-observation), not a calibrated score. Acceptable as a placeholder; must be labelled as such.
10. **No input validation** on ingestion (file size, path, type limits) — irrelevant for CLI, a security concern once uploads exist.

**Verdict:** The MVP is a well-structured *conceptual* prototype that correctly models the pipeline shape and provenance. It is **not** on the target substrate and must not be mistaken for it. The architecture is a good scaffold to *adapt*, not a system to *ship*.

---

## B. PRD vs Current Implementation Matrix

Legend: ✅ COMPLETE · 🟡 PARTIAL · ⛔ NOT STARTED · 🔧 NEEDS REFACTORING · 🔮 FUTURE/OPTIONAL

| Requirement | Status | Existing Implementation | Gap | Recommended Action |
|---|---|---|---|---|
| **FR-1** User mgmt (register/login/authz/roles/libraries) | ⛔ | none | No backend, no auth, no per-user isolation | M1 (FastAPI + auth), M3 (persist users) |
| **FR-2** Document upload (single/multi/folder) | 🟡 | CLI `ingest` of file/folder | No API upload, no per-user library, no size/type guards | M2 |
| **FR-3** Auto processing (OCR/layout/tables/charts/eq/lang) | 🟡 | text extraction for txt/md/html/pdf/docx | No OCR, layout, tables, charts, equations, language detection | M4 (core) + 🔮 multimodal |
| **FR-4** Knowledge extraction (entities/types) | 🟡→🔧 | LLM extractor + Pydantic schema | No aliases, weak entity resolution, no structured-output enforcement | M6 |
| **FR-5** Relationship discovery (typed, invented) | 🟡 | LLM relations w/ evidence+confidence | Endpoints only substring-linked; no dedup across aliases | M6 |
| **FR-6** KG construction (nodes/edges/merge/provenance/confidence/evolution) | 🟡→🔧 | pure-Python graph w/ merge+provenance+confidence | Not Neo4j; merge is naive; no Cypher/traversal engine | M7 (Neo4j) |
| **FR-7** Hybrid retrieval (graph+vector+keyword+metadata+citation) | 🟡→🔧 | fuses TF-IDF + graph neighborhood + provenance | TF-IDF ≠ dense; no metadata filter; concatenation, not ranked fusion | M5, M8 |
| **FR-8** QA (fact/reasoning/compare/analytical/summary/multi-doc/relationship) | 🟡 | single-shot grounded QA w/ evidence | No query-intent routing, no true multi-hop | M9 |
| **FR-9** Cross-document reasoning (combine/conflict/both views) | 🟡 | prompt asks for conflicts; neighborhood spans docs | No explicit multi-hop traversal or evidence-graph reasoning | M9 |
| **FR-10** Multilingual (any-lang docs/queries/answers) | 🟡 | answer language is a parameter | No language detection, untested cross-lingual retrieval | M11 |
| **FR-11** Conversation memory (coref across turns) | 🟡 | `chat` keeps history in prompt | No persistence, no reference-resolution eval | M12 |
| **FR-12** Explainability (citations/confidence/evidence/path/explanation) | 🟡→🔧 | returns all five fields | Citations chunk-level only (no page/section); confidence uncalibrated | M10 |
| **FR-13** Graph visualization | ⛔ | none | No UI | M14 |
| **FR-14** Incremental updates (change detection, partial update) | 🟡 | stores merge on re-ingest (append-only) | No change detection, no versioning, no delete/supersede | M13 |
| **FR-15** Export (graph/summary/citations/entities/relationships) | 🟡 | graph+vectors persisted as JSON | No user-facing export endpoints/formats | folded into M14/M15 |
| **NFR** Scalability (M entities, K users) | ⛔ | in-memory JSON | Won't scale past a few docs | M3/M5/M7 substrates |
| **NFR** Performance (immediate processing, low latency) | 🟡 | synchronous | No async, no background jobs, O(N) rebuilds | M4/M8 |
| **NFR** Reliability (no loss, recovery, versioning, backup) | ⛔ | single JSON file | No transactions, no versioning | M3/M7 |
| **NFR** Security (authn, RBAC, encryption, tenant isolation) | ⛔ | none | Entire area open | M1/M3 |
| **NFR** Maintainability (modular, replaceable LLM/graph DB) | ✅ | interfaces + isolated LLM | Interfaces need formalizing (Protocol/ABC) | M0/M5/M7 |
| **AI** NER / linking / RE / graph / multi-hop / summarize / translate / cite / hallucination / confidence | 🟡 | most present in prototype form | Linking, multi-hop, hallucination detection, calibrated confidence are weak | M6/M9/M15 |

---

## C. Mentor Build Order vs Current Implementation

The mentor's build order is **foundation-first**. The current MVP is **AI-pipeline-first on toy substrates** — it reached steps 6–10 in *prototype* form while skipping the real foundations of steps 1–7.

| Mentor build step | Current state | Reality |
|---|---|---|
| 1. User Login & Document Upload | ⛔ / 🟡 | CLI ingest only; no login, no upload API |
| 2. Text Extraction | ✅ (prototype) | Works for txt/md/html/pdf/docx |
| 3. Store Documents & Metadata in MySQL | ⛔ | JSON only; no relational DB |
| 4. Generate Embeddings | ⛔ | TF-IDF, not embeddings |
| 5. Store Embeddings in ChromaDB | ⛔ | JSON vector file |
| 6. Extract Entities & Relationships (LLM) | 🟡 | Done in prototype; needs entity resolution |
| 7. Build Knowledge Graph in Neo4j | ⛔ | Pure-Python graph, not Neo4j |
| 8. Hybrid Retrieval | 🟡 | Prototype fusion; not dense, not ranked |
| 9. Chat Interface | 🟡 | CLI `chat`; no web UI |
| 10. Citations & Graph Visualization | 🟡 / ⛔ | Citations yes (chunk-level); viz no |

**Interpretation:** The prototype is valuable because it de-risked the *shape* of steps 6–10 and proved provenance flows end-to-end. But per the mentor's philosophy ("every feature must work before moving on", "learn only what the current milestone needs"), we now **rebuild bottom-up on real substrates**, reusing the prototype's interfaces and prompts rather than its storage. The learning order (MySQL → FastAPI → LLM → embeddings → Neo4j → RAG) will be honored.

---

## D. Architecture Assessment

**Current architecture:** a single in-process Python library + CLI. Stores are in-memory objects serialized to JSON. The LLM is the only external service. This is a *monolith-as-library*.

**Target architecture (mentor diagram):**

```
User → FastAPI → { MySQL (metadata/users), ChromaDB (embeddings), Neo4j (graph) }
                          → Hybrid Retrieval → LLM → Cited/Explainable Answer
```

**Assessment & recommended deviations (with reasons):**

1. **Formalize the two existing abstractions into interfaces (Protocol/ABC) before swapping implementations.** The prototype already has `VectorStore` and `KnowledgeGraph` classes; turning them into interfaces with a `TFIDF`/`JSON` reference impl and a `Chroma`/`Neo4j` production impl lets us swap backends without touching retrieval/QA. *Why:* directly satisfies the PRD's "replaceable graph DB / LLM backend" NFR and keeps each milestone small.

2. **Introduce a service/repository layer between FastAPI and the databases.** Keep DB access (SQLAlchemy models, Chroma client, Neo4j driver) out of route handlers and out of business logic. *Why:* the mentor's rule "keep database operations separate from business logic" and testability.

3. **Do NOT introduce all three databases at once.** Sequence them: MySQL (M1, with users) → ChromaDB (M5) → Neo4j (M7), each fully working before the next. Use a **`docker-compose.yml`** for MySQL and Neo4j so local Windows setup is reproducible (ChromaDB can run embedded/local). *Why:* avoids a multi-database big-bang and matches "every feature must work before the next." (MySQL is pulled forward into M1 so auth/users persist to it directly — no interim SQLite/in-memory store is built and discarded.)

4. **Adopt async FastAPI + a background task/queue for ingestion.** Document processing + per-chunk LLM calls are slow; the upload endpoint should return immediately and process in the background (start with FastAPI `BackgroundTasks`, graduate to a real queue only if needed). *Why:* NFR "processing should begin immediately"; avoid premature microservices.

5. **Keep the CLI.** It becomes an ops/dev tool that calls the same service layer the API uses. *Why:* free integration-test surface; no reason to remove working code.

6. **Embedding provider is a decision to make now (see H).** Cloud (Voyage) vs local (sentence-transformers). Either sits behind the `VectorStore`/embedding interface.

**No LangChain** until explicitly approved — we build the retrieval loop ourselves (mentor mandate).

---

## E. Keep / Adapt / Replace / Remove

| Component | Decision | Rationale / What changes |
|---|---|---|
| `config.py` | **ADAPT** | Move to `pydantic-settings`; add DB URLs, embedding config, secrets via env. Keep the single-source-of-truth idea. |
| `llm.py` | **KEEP + ADAPT** | Keep as the sole LLM interface. Add: token/cost tracking, model tiering (cheap vs strong), optional response caching, typed error handling, retries. |
| `ingestion/loaders.py` | **KEEP** | Solid. Later add an OCR/layout interface behind the same `load_document` contract (M4). |
| `ingestion/chunker.py` | **KEEP + ADAPT** | Add token-based sizing and section awareness; keep the interface. |
| `extraction/schema.py` | **ADAPT** | Add `aliases`, richer provenance, entity-type normalization. |
| `extraction/extractor.py` | **ADAPT** | Add entity resolution, enforce structured output, stronger validation; keep the prompt as a starting point. |
| `graph/store.py` | **ADAPT → interface + reference impl** | Extract a `GraphStore` interface. Keep pure-Python impl as a test/reference backend. Neo4j becomes the production impl (M7). |
| `vectorstore/store.py` | **ADAPT (interface) + REPLACE (impl)** | Keep the `VectorStore` interface. Replace TF-IDF body with dense embeddings + ChromaDB (M5). |
| `retrieval/hybrid.py` | **ADAPT** | Keep the fusion concept; add ranked fusion (e.g., RRF), metadata filtering, dense retrieval, real graph queries. |
| `qa/answer.py` | **KEEP + ADAPT** | Keep the grounded, cited, JSON-structured answer contract. Add query routing + multi-hop (M9), finer citations (M10). |
| `pipeline.py` | **ADAPT → service layer** | Becomes the ingestion/query service used by both API and CLI; writes status to MySQL. |
| `cli.py`, `__main__.py` | **KEEP** | Retain as dev/ops + integration-test tool over the service layer. |
| `README.md` | **ADAPT** | Track architecture as it evolves. |
| `data/store/*.json` | **REMOVE (from VCS)** | Gitignore; real state moves to databases. Keep JSON backend only for the reference graph impl/tests. |
| sample data | **KEEP** | Useful for demos and tests; add a small multilingual sample later (M11). |

**Nothing is thrown away wholesale.** The prototype's interfaces, prompts, provenance model, and pipeline shape are the reusable core.

---

## F. Complete Milestone Roadmap

> Each milestone is small enough to finish, test, and commit independently. Fields omitted (e.g., "API changes: none") mean no change in that dimension.

### Milestone 0 — Foundation, Git & Conventions
- **Objective:** Put the existing code under version control with proper hygiene and a test scaffold; establish conventions.
- **Why:** Mentor mandate (Git from Day 1); make every later milestone a clean commit; enable reproducible tests.
- **Concepts to understand:** Git basics (init, branch, commit, remote, `.gitignore`), virtual environments, `pytest` basics, project layout.
- **Files affected:** new `.gitignore`, `tests/`, `pytest.ini`/`pyproject.toml`, `pin` `requirements.txt`; keep code as-is.
- **Dependencies:** none.
- **Implementation tasks:** `git init` + first commit; `.gitignore` (`.env`, `data/store/`, `__pycache__/`, venv); create GitHub repo + push; convert ad-hoc smoke tests into `tests/` (chunker, graph merge, vector search, persistence roundtrip); add a `venv` + `requirements` freeze; document conventions in README/CONTRIBUTING.
- **Tests:** the migrated smoke tests run green under `pytest`.
- **Acceptance:** repo on GitHub; `pytest` passes; `.env` and `data/store` are untracked; clean `git status`.
- **Demo:** clone-free `pytest` run; GitHub repo with a sensible commit.
- **Risks:** accidentally committing secrets/state (mitigated by `.gitignore` first).
- **Complexity:** Low.

### Milestone 1 — Backend Foundation + MySQL + User System
- **Objective:** Stand up FastAPI **and MySQL together**, and implement user registration/login/auth (JWT) persisted to MySQL from day one — no interim SQLite/in-memory store to throw away.
- **Why:** FR-1; everything user-facing hangs off this, and users are the first real relational entity, so MySQL belongs here (mentor's DB-first learning order).
- **Concepts:** FastAPI (routers, dependencies, Pydantic models), HTTP/REST, **relational modeling basics, SQLAlchemy ORM, Alembic migrations, Docker Compose for MySQL**, password hashing (argon2/bcrypt), JWT, dependency injection, request validation.
- **Files:** new `diris/api/` (app, routers, deps, security), `diris/services/`, `diris/db/` (engine, session, models), `docker-compose.yml` (MySQL), Alembic config; adapt `config.py` (DB URL).
- **Dependencies:** M0.
- **Implementation tasks:** `docker-compose` MySQL + SQLAlchemy engine/session + Alembic; `users` table + first migration; app factory + health route; `/auth/register`, `/auth/login` issuing JWT persisted-user-backed; `get_current_user` dependency; password hashing; input validation. **A repository layer keeps DB access out of route handlers.**
- **DB changes:** MySQL `users` table via Alembic migration (real, not interim).
- **API changes:** `/health`, `/auth/register`, `/auth/login`, `/me`.
- **Tests:** migration applies to a clean DB; register→login→access protected route; reject bad credentials/expired token; users persist across restart.
- **Acceptance:** a user can register and log in against **MySQL**, call a protected endpoint, and survive an app restart; unauthenticated calls are 401.
- **Demo:** hit the API via Swagger UI (register/login/`/me`); restart the app and show the user still exists in MySQL.
- **Risks:** Windows MySQL setup (mitigate with Docker); auth pitfalls (token expiry, hashing) — keep standard, don't invent crypto; migration discipline from the start.
- **Complexity:** Medium–High.

### Milestone 2 — Document Upload & Library
- **Objective:** Authenticated document upload into per-user libraries with validation and stored metadata (metadata store still interim until M3).
- **Why:** FR-2; feeds the whole pipeline.
- **Concepts:** multipart uploads, file validation (type/size), safe storage paths, per-user scoping.
- **Files:** `diris/api/routers/documents.py`, `diris/services/documents.py`, storage helper; reuse `ingestion/loaders.py`.
- **Dependencies:** M1.
- **Implementation tasks:** `POST /documents` (multipart), list/get/delete; validate type & size; store file under a per-user path; **persist a `documents` + `document_metadata` row to MySQL** (Alembic migration); do NOT process yet (that's M4).
- **DB changes:** MySQL `documents` and `document_metadata` tables via migration (FK to `users`).
- **API changes:** `/documents` CRUD scoped to the current user.
- **Tests:** upload valid/invalid files; rows land in MySQL; a user cannot see another user's documents.
- **Acceptance:** authenticated upload returns a document id; listing shows only the caller's docs; oversized/unsupported files are rejected.
- **Demo:** upload a PDF via Swagger; list it; try an unsupported file and see a clean 400.
- **Risks:** path traversal / unbounded size (validate strictly).
- **Complexity:** Medium.

### Milestone 3 — Processing Schema: Chunks & Status
- **Objective:** Extend the MySQL schema (stood up in M1–M2) with the relational bookkeeping the processing pipeline needs — `chunks` and `processing_status` — and finalize the repository layer. Additive; nothing is migrated or thrown away.
- **Why:** FR-3/14 + reliability NFR; chunks and processing state are relational data the pipeline (M4) reads and writes.
- **Concepts:** relational modeling depth (one-to-many, indexes, transactions, connection pooling), state machines in a schema, **what belongs in a relational DB vs a graph DB vs a vector DB**.
- **Files:** `diris/db/models.py` (+ chunk/status models), `diris/services/*`, new Alembic migration.
- **Dependencies:** M1, M2.
- **Implementation tasks:** `chunks` (FK to `documents`) and `processing_status` tables + migration; repository methods for chunk/status CRUD; transaction handling.
- **DB changes:** MySQL `chunks`, `processing_status` tables via migration.
- **Design note:** graph relationships (entity↔entity) do **not** go in MySQL — they belong in Neo4j (M7); embeddings belong in ChromaDB (M5). MySQL holds identities, ownership, status, and chunk bookkeeping. Document this placement rationale explicitly — it is a core learning goal of this milestone.
- **Tests:** migration applies; chunk/status CRUD via repositories; FK/isolation constraints hold; rollback on failure.
- **Acceptance:** chunks and processing status persist in MySQL with correct FKs; per-user isolation holds through the repository layer.
- **Demo:** show the full schema (users→documents→chunks + status) and explain what lives where and why.
- **Risks:** migration discipline; keeping DB access confined to the repository layer.
- **Complexity:** Medium.

### Milestone 4 — Document Processing Pipeline
- **Objective:** Robust, status-tracked processing: extract text (pdf/docx/txt/md/html), chunk, persist chunks + status; define interfaces for future OCR/tables/equations without building them.
- **Why:** FR-3; produces the units embeddings and extraction consume.
- **Concepts:** processing pipelines, background tasks, idempotency, status state machines, interface design for future extractors.
- **Files:** adapt `ingestion/*`, `pipeline.py` → processing service; `diris/api` background trigger.
- **Dependencies:** M3.
- **Implementation tasks:** on upload, enqueue processing (FastAPI `BackgroundTasks`); extract → chunk → write chunks + status transitions (`pending→processing→done/failed`); language detection stub; define `OCRProvider`/`LayoutProvider` interfaces (unimplemented).
- **DB changes:** populate `chunks`, update `processing_status`.
- **AI/LLM changes:** none yet (extraction is M6).
- **Tests:** upload → chunks appear; failure marks status `failed` without crashing; re-processing is idempotent.
- **Acceptance:** an uploaded document is asynchronously processed into persisted chunks with observable status.
- **Demo:** upload a PDF, poll status until `done`, list its chunks.
- **Risks:** background-task error handling; partial failures. Log and mark status.
- **Complexity:** Medium.

### Milestone 5 — Dense Embeddings + ChromaDB
- **Objective:** Replace TF-IDF with real dense embeddings stored/queried in ChromaDB, behind the existing `VectorStore` interface.
- **Why:** FR-7; the mentor's steps 4–5; semantic retrieval that beats lexical.
- **Concepts:** embeddings, vector dimensions, cosine/L2 similarity, ANN indexing, ChromaDB collections, metadata filtering, chunk↔embedding linkage.
- **Files:** new `ChromaVectorStore` implementing `VectorStore`; embedding client; config; retire TF-IDF to a reference/test backend.
- **Dependencies:** M4 (chunks), embedding-provider decision (H).
- **Implementation tasks:** formalize `VectorStore` interface; embed chunks on processing; upsert to Chroma with metadata (doc_id, chunk_id, user_id); `search` returns scored chunks; metadata filtering by user.
- **DB changes:** Chroma collection(s); MySQL stores embedding status/model.
- **AI/LLM changes:** embedding-model calls (separate from the chat model).
- **Tests:** semantic query returns relevant chunks; user metadata filter isolates results; interface swap doesn't break retrieval callers.
- **Acceptance:** dense retrieval returns semantically relevant chunks scoped to the user; TF-IDF removed from the hot path.
- **Demo:** ask a paraphrased query (no keyword overlap) and get the right chunk.
- **Risks:** embedding cost/latency; dimension mismatch on model change (store the model id).
- **Complexity:** Medium.

### Milestone 6 — Entity & Relationship Extraction (+ Resolution)
- **Objective:** Strengthen extraction: entities with types/aliases/descriptions, typed relationships with evidence/confidence/provenance, and **entity resolution** beyond substring matching.
- **Why:** FR-4/5; graph quality depends entirely on this.
- **Concepts:** structured LLM output/validation, NER vs entity linking, coreference, canonicalization, blocking/candidate generation, embedding-based similarity for resolution, confidence handling.
- **Files:** adapt `extraction/*`; new resolution module; persist extraction results (interim in MySQL, materialized to Neo4j in M7).
- **Dependencies:** M4 (chunks), M5 (embeddings, reused for resolution).
- **Implementation tasks:** enforce structured output; capture aliases; resolution pipeline (normalize → candidate match via alias + embedding similarity → merge with context check); keep provenance per mention; validate and drop/flag low-confidence junk.
- **AI/LLM changes:** stronger extraction prompt; embeddings reused for candidate matching; consider a cheaper model for extraction, stronger for adjudication.
- **Tests:** "Neil Armstrong"/"Armstrong"/"N. Armstrong" resolve to one entity *when context supports it* and stay separate when it doesn't; malformed LLM output handled; provenance preserved.
- **Acceptance:** extraction yields resolved entities with aliases and traceable evidence; naive-substring failures from the MVP are gone.
- **Demo:** ingest a doc using multiple name forms; show one merged entity with aliases + sources.
- **Risks:** over-merging (false positives) is worse than under-merging; require evidence and a confidence threshold.
- **Complexity:** High.

### Milestone 7 — Neo4j Knowledge Graph
- **Objective:** Make Neo4j the real graph backend behind a `GraphStore` interface: node/relationship schema, provenance, confidence, merge, Cypher queries, traversal.
- **Why:** FR-6/9; the mentor's step 7.
- **Concepts:** property graphs, Cypher (`MERGE`, `MATCH`, variable-length paths), constraints/indexes, provenance modeling, driver sessions/transactions.
- **Files:** new `Neo4jGraphStore` implementing `GraphStore`; keep pure-Python impl as reference/test; `docker-compose.yml` adds Neo4j.
- **Dependencies:** M6 (resolved entities), M3 (doc/chunk ids for provenance).
- **Implementation tasks:** schema + uniqueness constraints; `MERGE` entities/edges idempotently; store confidence + provenance (chunk/doc refs); neighborhood/path Cypher queries; migrate the graph interface's callers to Neo4j.
- **DB changes:** Neo4j graph; MySQL keeps identities/ownership and references.
- **Tests:** idempotent merge (re-ingest doesn't duplicate); neighborhood/path queries match expectations; provenance retrievable from an edge.
- **Acceptance:** entities/relationships live in Neo4j with provenance+confidence; graph queries work via Cypher; re-ingest is idempotent.
- **Demo:** run a Cypher query in Neo4j Browser showing a cross-document neighborhood with provenance.
- **Risks:** Neo4j learning curve; merge semantics. Start with a tiny schema.
- **Complexity:** High.

### Milestone 8 — Hybrid Retrieval (ranked fusion)
- **Objective:** Combine dense vector + keyword + graph + metadata retrieval with a real ranking/fusion strategy (not concatenation).
- **Why:** FR-7; the PRD's core differentiator.
- **Concepts:** lexical vs dense retrieval, graph-based retrieval, rank fusion (e.g., Reciprocal Rank Fusion), metadata filtering, deduplication, evidence selection.
- **Files:** adapt `retrieval/hybrid.py` to query Chroma + Neo4j + MySQL metadata; add a fusion/ranker.
- **Dependencies:** M5, M7.
- **Implementation tasks:** dense search (Chroma) + optional keyword search + graph-seeded chunk retrieval (via entities in query → Neo4j neighborhood → provenance chunks) + metadata filters; fuse with RRF/weighted scoring; dedupe; return a ranked evidence bundle with per-source scores.
- **Tests:** fusion beats any single retriever on a small labelled query set; user metadata isolation holds; deterministic ranking given fixed inputs.
- **Acceptance:** for queries needing cross-document/graph links, hybrid retrieval surfaces evidence that pure vector search misses, with an explainable ranking.
- **Demo:** a query where the answer needs a graph hop; show which evidence came from which retriever.
- **Risks:** fusion tuning; over-fetching cost. Keep top-k bounded.
- **Complexity:** High.

### Milestone 9 — RAG + Multi-hop Reasoning
- **Objective:** Real QA pipeline: query understanding → retrieval → graph traversal → evidence fusion → multi-step reasoning → grounded answer.
- **Why:** FR-8/9; the product's payoff.
- **Concepts:** query intent classification, multi-hop reasoning over a graph, evidence-grounded generation, answer typing (fact/compare/summary/analytical).
- **Files:** adapt `qa/answer.py`; add query-understanding + reasoning orchestration over M8 retrieval.
- **Dependencies:** M8.
- **Implementation tasks:** classify query type; route retrieval accordingly; for relational/multi-hop questions, traverse Neo4j and assemble an evidence chain; fuse with vector evidence; reason step-by-step; generate grounded answer; keep it model-agnostic behind `llm.py`.
- **AI/LLM changes:** reasoning prompt(s); model tiering (cheap for routing, strong for reasoning).
- **Tests:** fact, comparison ("compare X and Y"), multi-hop ("head of the house that Harry belongs to"), summary, multi-document — each returns grounded, correct answers on the sample corpus.
- **Acceptance:** the six PRD question types work and stay grounded in retrieved evidence; multi-hop questions demonstrably use graph traversal.
- **Demo:** the Harry Potter multi-hop chain answered correctly with evidence.
- **Risks:** reasoning cost/latency; hallucination on thin evidence (require grounding + low-confidence fallback).
- **Complexity:** High.

### Milestone 10 — Citations & Provenance
- **Objective:** Every factual claim traceable to document/section/chunk (+ graph evidence), with no fabricated citations.
- **Why:** FR-12; trust and explainability.
- **Concepts:** provenance propagation, citation formatting, page/section tracking from M4 processing, faithfulness checking.
- **Files:** adapt `qa/answer.py` + retrieval to carry section/page metadata; citation renderer.
- **Dependencies:** M9; needs M4 to have captured section/page metadata.
- **Implementation tasks:** thread doc/section/page/chunk metadata through retrieval into answers; validate that every citation id exists in the retrieved set (drop/flag hallucinated ones); render human-readable citations + graph-evidence references.
- **Tests:** every returned citation resolves to a real retrieved chunk; a synthetic hallucinated citation is caught; section/page appear when available.
- **Acceptance:** answers cite real, resolvable sources at chunk (and section/page where available) granularity; fabricated citations are impossible to emit.
- **Demo:** an answer whose citations you can click through to the exact source text.
- **Risks:** metadata gaps (some formats lack pages) — degrade gracefully.
- **Complexity:** Medium.

### Milestone 11 — Multilingual QA
- **Objective:** Multilingual documents and queries; user-selected answer language; cross-language retrieval where sensible (e.g., English doc → Hindi question → Hindi answer → English citations).
- **Why:** FR-10.
- **Concepts:** language detection, multilingual embeddings, cross-lingual retrieval, translation vs. multilingual generation.
- **Files:** language detection in processing (M4 hook) and query; ensure the embedding model is multilingual or add translation; answer-language parameter (already present) wired to the API.
- **Dependencies:** M5 (embeddings), M9 (QA).
- **Implementation tasks:** detect doc/query language; choose a multilingual embedding model or translate queries; answer in the requested language while citing sources in their original language.
- **Tests:** English-doc + Hindi-question → correct Hindi answer with English citations; language auto-detected.
- **Acceptance:** the cross-lingual example works end-to-end; answer language is user-controlled.
- **Demo:** the English→Hindi example live.
- **Risks:** embedding model must be multilingual, or cross-lingual recall drops. Decide during M5.
- **Complexity:** Medium.

### Milestone 12 — Conversation Memory
- **Objective:** Persistent multi-turn context with correct reference resolution across turns.
- **Why:** FR-11.
- **Concepts:** conversation state, coreference resolution across turns, context-window management, session storage.
- **Files:** conversation store (MySQL), session-aware QA endpoint; adapt `qa`.
- **Dependencies:** M9, M3.
- **Implementation tasks:** persist per-session turns; resolve references ("he", "that house") against prior turns + graph; manage context growth (summarize/trim); session endpoints.
- **DB changes:** `conversations`, `messages` tables.
- **Tests:** the three-turn Harry Potter chain resolves "he"/"that house"/"head of that house" correctly; sessions persist across restarts.
- **Acceptance:** contextual references resolve correctly across turns and survive a restart.
- **Demo:** the three-turn chain in the chat UI/API.
- **Risks:** unbounded context growth (mitigate with summarization/trimming).
- **Complexity:** Medium.

### Milestone 13 — Incremental Updates & Versioning
- **Objective:** Detect document changes and update only affected chunks/entities/relationships instead of rebuilding.
- **Why:** FR-14; performance + reliability NFRs.
- **Concepts:** content hashing, diffing, versioning, targeted invalidation across three stores, idempotency.
- **Files:** processing service (change detection), store deletes/updates for MySQL/Chroma/Neo4j.
- **Dependencies:** M4, M5, M7.
- **Implementation tasks:** hash chunks/sections; on re-upload, diff against stored version; re-embed/re-extract only changed chunks; supersede/delete stale embeddings + graph elements; keep provenance consistent; version records.
- **DB changes:** version columns; soft-delete/supersede semantics across stores.
- **Tests:** changing one section updates only its chunks/entities; unchanged knowledge is preserved; no orphaned embeddings/edges.
- **Acceptance:** editing part of a document updates only the affected knowledge, verifiably.
- **Complexity:** High.

### Milestone 14 — Graph Visualization & Export
- **Objective:** A user-accessible graph explorer (entities, relationships, neighborhoods, provenance, paths) that doesn't dominate the chat UI; plus export (graph/entities/relationships/citations/summary).
- **Why:** FR-13, FR-15.
- **Concepts:** graph data APIs, front-end graph rendering (e.g., a JS graph lib), pagination/limits for large graphs.
- **Files:** graph API endpoints (from Neo4j), a graph view in the UI, export endpoints.
- **Dependencies:** M7, plus a web UI (introduced alongside the chat interface).
- **Implementation tasks:** endpoints for neighborhood/path/entity detail with provenance; a separate "Graph" section in the UI; export in JSON/CSV/GraphML.
- **Tests:** neighborhood/path endpoints return correct subgraphs with provenance; exports are well-formed; large graphs are bounded/paginated.
- **Acceptance:** a user can inspect an entity's neighborhood and provenance visually, and export knowledge artifacts.
- **Complexity:** Medium–High.

### Milestone 15 — Testing, Evaluation & Hardening
- **Objective:** Systematic evaluation and robustness across the whole system.
- **Why:** Definition of Done at the product level; PRD success metrics.
- **Concepts:** retrieval metrics (precision/recall/MRR), extraction eval, citation-correctness eval, hallucination testing, load/perf testing.
- **Files:** `tests/eval/`, fixtures, small labelled datasets, CI.
- **Dependencies:** all prior.
- **Implementation tasks:** eval sets for retrieval/extraction/citations; hallucination-resistance and conflicting-source tests; multilingual + incremental-update tests; multi-user isolation tests; large-document ingestion; failure-injection tests; wire into CI.
- **Acceptance:** documented metrics for each PRD success dimension; known failure modes covered by tests; CI green.
- **Complexity:** High.

### Milestone 16 — Frontend UI  *(added on request; details TBD after M15)*
- **Objective:** A web frontend over the existing REST API so the system is usable without Swagger — login/register, document upload + library with processing status, a chat interface for grounded Q&A with inline citations, a graph-visualization view, and (optionally) multilingual + conversation UI.
- **Why:** Everything through M15 is a backend/API; a UI makes it demoable and usable by non-technical users (FR-13 visualization, general UX).
- **Concepts (to scope later):** a frontend stack (React/Vue or server-rendered), auth/token handling in the client, file upload UX, streaming/polling for processing status, a graph rendering lib (e.g. Cytoscape/vis-network/D3), rendering citations and confidence.
- **Dependencies:** M1–M12 (APIs), ideally M14 (graph viz API).
- **Decided (2026-08-24):** **React + Vite + TypeScript + Tailwind CSS**, React Router, vis-network for the graph; **Full scope**, phased. Backend gets `CORSMiddleware` in phase 16.1.
- **Phases:** 16.1 scaffold + auth + CORS · 16.2 documents (upload/library/status/replace) · 16.3 chat (grounded, cited, conversation memory, answer-language) · 16.4 graph explorer (full/neighborhood/path/export) · 16.5 hybrid search + entity browser.
- **Testing:** verified live in the browser pane per phase (optional Vitest for API-client logic).
- **Complexity:** High (multi-screen SPA).

---

## G. Dependency Graph Between Milestones

```
M0 ─ foundation/git
      │
      ▼
M1 ─ FastAPI + MySQL + auth (users table)
      │
      ▼
M2 ─ upload + library (documents/metadata in MySQL)
      │
      ▼
M3 ─ processing schema (chunks + status tables)
      │
      ▼
M4 ─ processing pipeline (populates chunks + status)
      ├───────────────┐
      ▼               ▼
M5 ─ embeddings     (M6 also needs M5)
   + ChromaDB
      │               │
      ▼               ▼
M6 ─ extraction + resolution  (uses M4 chunks + M5 embeddings)
      │
      ▼
M7 ─ Neo4j graph (needs M6 entities, M3 refs)
      │
      ▼
M8 ─ hybrid retrieval (needs M5 + M7)
      │
      ▼
M9 ─ RAG + multi-hop (needs M8)
      ├──────────────┬───────────────┐
      ▼              ▼               ▼
M10 citations    M11 multilingual  M12 conversation memory
 (needs M9,M4)    (needs M5,M9)      (needs M9,M3)
      │
      ▼
M13 incremental updates (needs M4,M5,M7)
      │
      ▼
M14 graph viz + export (needs M7 + web UI)
      │
      ▼
M15 evaluation & hardening (needs all)
```

**Critical path:** M0→M1→M2→M3→M4→M5→M6→M7→M8→M9. M10/M11/M12 branch off M9 and can be reordered. M13/M14/M15 come late.

---

## H. Risks & Technical Decisions

**Decisions to make before/at the relevant milestone:**
1. **Embedding provider (M5):** Cloud **Voyage AI** (high quality, another API key, per-call cost) vs local **sentence-transformers** (free, offline, heavier install, uses your machine). *Recommendation:* start local (`sentence-transformers`, a multilingual model to also serve M11) to control cost and simplify; the interface makes switching trivial. Decide explicitly at M5.
2. **Local infra (M3/M7):** **Docker Compose** for MySQL + Neo4j (reproducible on Windows) vs native installs. *Recommendation:* Docker Compose.
3. **ORM/migrations (M3):** SQLAlchemy + Alembic (standard, well-documented). *Recommendation:* yes.
4. **Auth (M1):** JWT with hashed passwords (argon2/bcrypt). Keep standard; no custom crypto.
5. **Sync vs async ingestion (M4):** FastAPI `BackgroundTasks` first; a real queue (RQ/Celery) only if load demands it — avoid premature microservices.
6. **Chat model tiering:** cheap model for routing/simple extraction, strong model for reasoning/adjudication; configurable per stage (cost awareness).

**Cross-cutting risks:**
- **Cost blow-up** from per-chunk LLM calls → cache, batch, tier models, cap top-k, avoid reprocessing (M13).
- **Windows dev friction** with three databases → Docker Compose, one DB at a time.
- **Entity over-merging (M6)** is the subtlest correctness risk → require evidence + thresholds; prefer under-merging.
- **Neo4j + Cypher learning curve (M7)** → start with a tiny schema and a handful of query patterns.
- **Scope creep** → the milestone rules forbid building ahead; keep the system working after each.
- **Hallucination/fake citations (M9/M10)** → validate citations against retrieved evidence; surface low confidence.

---

## I. Recommended Immediate Next Milestone

**Milestone 0 — Foundation, Git & Conventions.**

Reasons: (1) the mentor mandates Git from Day 1 and there is currently no repository; (2) it's low-risk and fast; (3) it converts the throwaway smoke tests into a real `tests/` suite so every later milestone has a safety net; (4) it prevents secret/state leakage via `.gitignore` before any of that exists. It touches no application logic, so it can't break the working MVP.

After M0, the natural next step is **M1 (FastAPI + auth)** — but per the rules I will wait for explicit approval before starting either.

---

## J. Definition of Done — Milestone 0

M0 is complete only when **all** of the following hold:
1. A Git repository is initialized and pushed to GitHub with a sensible initial commit history (not one giant commit).
2. `.gitignore` excludes `.env`, `data/store/`, `__pycache__/`, virtualenvs, and editor cruft; `git status` is clean and **no secrets or generated state are tracked**.
3. The existing MVP still runs unchanged (`python -m diris stats`, `ingest`, `ask`) — no functionality regressed.
4. Ad-hoc smoke tests are migrated into a committed `tests/` suite (chunker, graph merge/dedup, vector search, persistence roundtrip) and **`pytest` passes**.
5. `requirements.txt` reflects the real, working dependency set; setup steps are documented in the README.
6. Project conventions (branching, commit-message style, how to run tests) are written down.
7. You can explain what was set up and why (Git workflow, ignore rules, test scaffold).

---

*Next action: await explicit "Start Milestone 0" (or another milestone) before writing any code.*
