"""WS /v1/sessions/{session_id}/stream -- realtime relay to Agent Engine
(docs/backend/02_BACKEND_PROCESS_DRAFT.md §5, §6.3).

Runs two concurrent tasks for the lifetime of the connection: one reading
frames from the client and forwarding them into the Agent Engine live
session (upstream), and one reading events from the Agent Engine live
session and forwarding them to the client (downstream) -- the same pattern
as google/adk-samples/python/agents/bidi-demo.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from ..middleware.auth import consume_stream_ticket
from ..services import firestore_client
from ..services.agent_engine_client import AgentLiveSession

router = APIRouter(tags=["ws"])
logger = logging.getLogger("ws")

SESSIONS_COLLECTION = "sessions"
SESSION_MESSAGES_COLLECTION = "session_messages"
DISPLAY_EVENTS_COLLECTION = "display_events"


@router.websocket("/v1/sessions/{session_id}/stream")
async def stream(websocket: WebSocket, session_id: str, ticket: str) -> None:
    # App Check is enforced when the ticket is issued (POST .../stream-ticket
    # requires it), not here -- browsers' native WebSocket API can't attach a
    # custom header to the handshake, so re-checking at this layer would be
    # both redundant and unsatisfiable from a real browser client.
    if not consume_stream_ticket(ticket, session_id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    doc = firestore_client.get_document(SESSIONS_COLLECTION, session_id)
    if doc is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    agent_session = AgentLiveSession(doc["agent_session_id"])
    await agent_session.connect()

    sequence = 0

    async def send_event(event_type: str, **payload: object) -> None:
        nonlocal sequence
        sequence += 1
        await websocket.send_json(
            {
                "type": event_type,
                "event_id": uuid.uuid4().hex,
                "session_id": session_id,
                "sequence": sequence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            }
        )

    async def upstream() -> None:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            audio_bytes = message.get("bytes")
            if audio_bytes is not None:
                await agent_session.send_audio(audio_bytes)
                continue
            text_frame = message.get("text")
            if text_frame is not None:
                await _handle_client_event(json.loads(text_frame), agent_session, session_id)

    async def downstream() -> None:
        async for event in agent_session.events():
            if event.type == "audio_chunk" and event.audio is not None:
                await websocket.send_bytes(event.audio)
            elif event.type == "text_delta":
                await send_event("agent.text.delta", speaker_id=event.speaker_id, text=event.text)
                if event.speaker_id and event.text:
                    firestore_client.create_document(
                        DISPLAY_EVENTS_COLLECTION,
                        uuid.uuid4().hex,
                        {
                            "session_id": session_id,
                            "speaker_id": event.speaker_id,
                            "text": event.text,
                        },
                    )
            elif event.type == "turn_complete":
                await send_event("turn.complete", speaker_id=event.speaker_id)

    try:
        await send_event("session.ready")
        await asyncio.gather(upstream(), downstream())
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws.stream_error session_id=%s", session_id)
        try:
            await send_event("system.error", message="conversation stream failed")
        except Exception:  # noqa: BLE001 -- socket may already be gone
            pass
    finally:
        await agent_session.close()


async def _handle_client_event(
    data: dict, agent_session: AgentLiveSession, session_id: str
) -> None:
    event_type = data.get("type")

    if event_type in ("user.speech.start", "user.speech.end", "ping"):
        return  # floor-control/heartbeat only; audio itself arrives as binary frames

    if event_type == "user.text":
        text = data.get("payload", {}).get("text", "")
        if text:
            await agent_session.send_text(text)
            firestore_client.create_document(
                SESSION_MESSAGES_COLLECTION,
                uuid.uuid4().hex,
                {"session_id": session_id, "transcript": text},
            )
    elif event_type == "user.interrupt":
        await agent_session.send_interrupt()
