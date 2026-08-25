"""SQLAlchemy engine, session factory, and the FastAPI DB dependency.

`Base` is the declarative base every ORM model inherits from; Alembic reads
`Base.metadata` to know the target schema.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import settings

# pool_pre_ping avoids handing out a dead connection after MySQL drops idle ones.
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """Yield a request-scoped session and always close it. Used via Depends()."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
