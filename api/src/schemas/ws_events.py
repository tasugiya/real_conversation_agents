"""WebSocket JSON text-frame event envelope (docs/backend/02_BACKEND_PROCESS_DRAFT.md §5.3).

Binary audio chunks are sent as separate binary frames, not wrapped in this
envelope. This module only models the JSON control/subtitle/state frames.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# --- Server -> Client event type names ---
ServerEventType = Literal[
    "session.ready",
    "speaker.changed",
    "user.transcript.partial",
    "user.transcript.final",
    "agent.text.delta",
    "agent.text.final",
    "agent.interrupted",
    "turn.complete",
    "floor.opened",
    "hint.available",
    "session.state",
    "session.time_warning",
    "session.time_limit",
    "session.wrap",
    "session.ending",
    "session.resumed",
    "system.warning",
    "system.error",
    "pong",
]

# --- Client -> Server event type names (JSON frames only; audio is binary) ---
ClientEventType = Literal[
    "client.ready",
    "user.speech.start",
    "user.speech.end",
    "user.text",
    "user.interrupt",
    "session.end.request",
    "client.resume",
    "ping",
]


class WsEnvelope(BaseModel):
    type: str
    event_id: str
    session_id: str
    turn_id: str | None = None
    sequence: int
    timestamp: str
    speaker_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ClientEnvelope(BaseModel):
    """Inbound JSON frames only. Binary audio frames bypass this model entirely
    and are forwarded straight to the Agent Engine relay (see routes/ws.py)."""

    type: ClientEventType
    payload: dict[str, Any] = Field(default_factory=dict)
