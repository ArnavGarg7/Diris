# DIRIS Data Model — what lives where, and why

DIRIS uses three stores, each for the shape of data it's good at. The **chunk id
(and document id) is the join key** that ties them together.

| Data | Store | Why here |
|---|---|---|
| Users, ownership | **MySQL** | Identity, auth, relational integrity |
| Documents + file metadata | **MySQL** | Bookkeeping; the file *bytes* live on disk, this is the record |
| **Chunk text** | **MySQL** | System of record for the text; relational, transactional |
| Processing status + history | **MySQL** | State machine + audit trail; must be consistent/queryable |
| Chunk **embeddings** (vectors) | **ChromaDB** (M5) | Vector similarity search; keyed by the chunk id from MySQL |
| Entity ↔ entity **relationships** | **Neo4j** (M7) | Graph traversal / multi-hop reasoning |

**Rule of thumb:** if the question is "who owns what / what's the text / what state is it in," it's MySQL. If it's "what's *similar*," it's the vector store. If it's "what's *connected*," it's the graph.

## Relational schema (MySQL) as of M3

```
users
  └─< documents                 (one user → many documents)
        ├─< document_metadata    (one document → many key/value attrs)
        ├─< chunks               (one document → many ordered chunks)   ← M3
        └─< document_processing_status  (one document → many status events) ← M3
```

- `chunks`: `document_id` (FK, CASCADE), `chunk_index` (0-based; unique per document),
  `content` (the text), `char_count`, `created_at`. Inserted in **one transaction**
  per document so a document is never half-chunked.
- `document_processing_status`: append-only log of transitions
  (`uploaded → processing → done | failed`) with an optional `stage` and error
  `message`. The document's *current* state is also mirrored on `documents.status`
  for fast filtering; both are written together so they never disagree.

## Not in MySQL (on purpose)

- **Vectors** → ChromaDB (M5). We store the id linkage, not the 768/1024-dim arrays.
- **Graph edges** → Neo4j (M7). A relationship like `Curie —discovered→ Radium` is a
  graph traversal problem, not a relational one.
