"""Configuration loaded from environment / .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional; env vars still work without it
    pass


@dataclass(frozen=True)
class Settings:
    # LLM provider selection. "auto" picks the first provider with a key present,
    # in order: groq -> gemini -> anthropic (with the others as runtime fallbacks).
    llm_provider: str = os.getenv("DIRIS_LLM_PROVIDER", "auto")

    api_key: str | None = os.getenv("ANTHROPIC_API_KEY")          # anthropic
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")

    model: str = os.getenv("DIRIS_MODEL", "claude-opus-5")        # anthropic model
    groq_model: str = os.getenv("DIRIS_GROQ_MODEL", "openai/gpt-oss-120b")
    gemini_model: str = os.getenv("DIRIS_GEMINI_MODEL", "gemini-3.1-flash-lite")

    store_dir: Path = Path(os.getenv("DIRIS_STORE_DIR", "data/store"))

    # Chunking
    chunk_chars: int = 1400          # target characters per chunk
    chunk_overlap: int = 200         # overlap between consecutive chunks

    # Retrieval
    vector_top_k: int = 6
    graph_hops: int = 1              # neighborhood radius around matched entities

    # Database (MySQL). Driven entirely by env so Docker vs native is a URL swap.
    database_url: str = os.getenv(
        "DIRIS_DATABASE_URL", "mysql+pymysql://diris:diris@localhost:3307/diris"
    )

    # Auth / JWT. The secret MUST be overridden in .env for anything real.
    jwt_secret: str = os.getenv("DIRIS_JWT_SECRET", "dev-only-insecure-secret-change-me")
    jwt_algorithm: str = os.getenv("DIRIS_JWT_ALG", "HS256")
    jwt_expire_minutes: int = int(os.getenv("DIRIS_JWT_EXPIRE_MINUTES", "60"))

    # Vector store / embeddings (Milestone 5)
    chroma_dir: Path = Path(os.getenv("DIRIS_CHROMA_DIR", "data/chroma"))
    chroma_collection: str = os.getenv("DIRIS_CHROMA_COLLECTION", "diris_chunks")

    # Knowledge graph (Neo4j, Milestone 7)
    neo4j_uri: str = os.getenv("DIRIS_NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("DIRIS_NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("DIRIS_NEO4J_PASSWORD", "dirispassword")

    # Entity extraction & resolution (Milestone 6)
    extraction_model: str = os.getenv("DIRIS_EXTRACTION_MODEL", "claude-sonnet-5")
    chroma_entity_collection: str = os.getenv(
        "DIRIS_CHROMA_ENTITY_COLLECTION", "diris_entities"
    )
    # Cosine-similarity threshold for merging two entity names via embeddings.
    # High on purpose: we prefer under-merging (a missed merge) to a wrong merge.
    resolution_threshold: float = float(os.getenv("DIRIS_RESOLUTION_THRESHOLD", "0.83"))

    # Document uploads (Milestone 2)
    upload_dir: Path = Path(os.getenv("DIRIS_UPLOAD_DIR", "data/uploads"))
    max_upload_mb: int = int(os.getenv("DIRIS_MAX_UPLOAD_MB", "25"))
    allowed_extensions: frozenset[str] = frozenset(
        e.strip().lower()
        for e in os.getenv(
            "DIRIS_ALLOWED_EXTENSIONS", ".pdf,.docx,.txt,.md,.html"
        ).split(",")
        if e.strip()
    )

    def require_key(self) -> str:
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add "
                "your key, or export ANTHROPIC_API_KEY in your shell."
            )
        return self.api_key


settings = Settings()
