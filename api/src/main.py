"""FastAPI application entrypoint (docs/infra/01_ARCHITECTURE.md §3.2)."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routes import auth, health, sessions, topic_packs, topics, ws

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper())

app = FastAPI(title="real-conv-api")

# allow_origins must be an explicit list, not "*": browsers reject a wildcard
# origin whenever allow_credentials is True.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in settings.cors_allowed_origins.split(",") if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(topics.router)
app.include_router(topic_packs.router)
app.include_router(sessions.router)
app.include_router(ws.router)
