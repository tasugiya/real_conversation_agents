"""Client for the deployed conversation Agent Engine's LIVE conversation relay.

This is the highest-uncertainty integration point in the system: Agent
Engine's bidi/live streaming client surface has open reliability issues and
more than one documented calling convention as of this writing (some SDK
docs/examples show `agent_engines.get(...).async_stream_query(...)`, others
show `client.aio.live.agent_engines.connect(name=..., config={"class_method":
"bidi_stream_query"})`). The exact call is marked TODO below and MUST be
verified against the pinned google-cloud-aiplatform version the first time
this is exercised against the dev environment.

Review generation and Topic Pack generation deliberately do NOT go through
this client -- see services/gemini_client.py and routes/topic_packs.py.
Agent Engine is used only for the one thing Cloud Run can't do alone: a
managed, low-latency bidirectional Gemini Live session.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import vertexai
from vertexai import agent_engines

from ..config import get_settings


@dataclass
class AgentEvent:
    """Normalized event yielded to routes/ws.py, independent of whatever
    shape the underlying Agent Engine SDK actually returns."""

    type: str  # "text_delta" | "text_final" | "audio_chunk" | "turn_complete" | "error"
    speaker_id: str | None = None
    text: str | None = None
    audio: bytes | None = None


_initialized = False


def _ensure_init() -> None:
    global _initialized
    if _initialized:
        return
    settings = get_settings()
    vertexai.init(project=settings.gcp_project_id, location=settings.gcp_region)
    _initialized = True


async def create_agent_session(user_id: str) -> str:
    _ensure_init()
    settings = get_settings()
    engine = agent_engines.get(settings.agent_engine_resource_name)
    session = await engine.async_create_session(user_id=user_id)
    return session["id"] if isinstance(session, dict) else session.id


class AgentLiveSession:
    """One instance per user conversation session (one WebSocket lifetime)."""

    def __init__(self, agent_session_id: str) -> None:
        self._agent_session_id = agent_session_id
        self._connection: Any = None

    async def connect(self) -> None:
        _ensure_init()
        settings = get_settings()
        engine = agent_engines.get(settings.agent_engine_resource_name)

        # TODO(verify at first dev deploy): confirm the correct bidi call for
        # the installed SDK version and replace this. See module docstring.
        self._connection = await engine.async_live_connect(
            session_id=self._agent_session_id,
        )

    async def send_audio(self, chunk: bytes) -> None:
        await self._connection.send(audio=chunk)

    async def send_text(self, text: str) -> None:
        await self._connection.send(text=text)

    async def send_interrupt(self) -> None:
        await self._connection.send(interrupt=True)

    async def events(self) -> AsyncIterator[AgentEvent]:
        async for raw in self._connection.receive():
            yield _normalize_event(raw)

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()


def _normalize_event(raw: Any) -> AgentEvent:
    """Parse the "Alice: ..." / "Bob: ..." speaker-label convention from
    agent/src/prompts/root_instruction.py out of the text into speaker_id,
    since the single-agent (no sub_agents) design has no structural speaker
    field of its own.
    """
    text = getattr(raw, "text", None)
    speaker_id = None
    if text and ":" in text.split("\n", 1)[0]:
        label, _, rest = text.partition(":")
        if label.strip().lower() in ("alice", "bob"):
            speaker_id = label.strip().lower()
            text = rest.strip()

    if getattr(raw, "audio", None):
        return AgentEvent(type="audio_chunk", speaker_id=speaker_id, audio=raw.audio)
    if getattr(raw, "turn_complete", False):
        return AgentEvent(type="turn_complete", speaker_id=speaker_id)
    return AgentEvent(type="text_delta", speaker_id=speaker_id, text=text)
