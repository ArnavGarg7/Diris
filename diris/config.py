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
    api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    model: str = os.getenv("DIRIS_MODEL", "claude-opus-5")
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
