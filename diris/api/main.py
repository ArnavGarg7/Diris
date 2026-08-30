"""FastAPI application factory.

Run locally with:
    uvicorn diris.api.main:app --reload
Then open http://127.0.0.1:8000/docs for interactive Swagger UI.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import settings
from .routers import (
    auth,
    conversations,
    documents,
    entities,
    graph,
    qa,
    search,
    users,
)


def create_app() -> FastAPI:
    app = FastAPI(title="DIRIS API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    app.include_router(entities.router)
    app.include_router(qa.router)
    app.include_router(conversations.router)
    app.include_router(graph.router)
    return app


app = create_app()
