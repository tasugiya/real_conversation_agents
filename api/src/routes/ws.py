"""WS /v1/sessions/{session_id}/stream -- realtime relay to ADK runner
(docs/backend/02_BACKEND_PROCESS_DRAFT.md §5, §6.3).

Runs upstream, downstream, and a session timer concurrently using
asyncio.TaskGroup so that any task ending cancels the others and always
reaches the finally-close path (fixes BUG-004).

Turn Controller (MEMO 3.1):
  - Tracks AI consecutive turns; after 2 uninterrupted AI turns sends
    floor.opened to the client and a nudge to the agent to yield the floor.
  - Session timer fires session.time_warning at 80% of max duration and
    session.time_limit at the limit, then terminates the TaskGroup cleanly.

Session message persistence (fixes BUG-001/003):
  - User transcript finals saved with created_at, speaker_id='user', role='user'
  - AI text finals saved with created_at, speaker_id, role='assistant'
  Both fields are required by sessions.py:_load_transcript for Review.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from ..config import get_settings
from ..middleware.auth import consume_stream_ticket
from ..services import firestore_client
from ..services.agent_engine_client import AgentLiveSession

router = APIRouter(tags=["ws"])
logger = logging.getLogger("ws")

SESSIONS_COLLECTION = "sessions"
SESSION_MESSAGES_COLLECTION = "session_messages"
DISPLAY_EVENTS_COLLECTION = "display_events"
TOPIC_PACKS_COLLECTION = "topic_packs"

# Maximum AI consecutive turns before yielding floor back to the user.
_MAX_AI_CONSECUTIVE_TURNS = 2

# Nudge sent to the agent when it exceeds the consecutive-turn limit.
_FLOOR_YIELD_NUDGE = (
    "You have spoken several times in a row. "
    "Please pause and wait for the user to respond now."
)

# WS message rate limit (upstream frames per minute, including audio chunks).
_MAX_MSGS_PER_MIN = 100

# How many recent session_messages to replay to the agent on reconnect.
_RECONNECT_HISTORY_LIMIT = 8


class _SessionOver(Exception):
    """Raised by the ender() task to terminate the TaskGroup cleanly."""


def _finalize_session_update(
    current_status: str | None, graceful_end: bool, sequence: int
) -> dict:
    """Decide what the WS finally-block should write to the session doc.

    Always persists last_sequence (for reconnects). Only additionally frees
    the concurrency slot (status -> "abandoned") when the disconnect was an
    intentional end (time limit / client request / rate limit) AND the
    session is still "created" -- never on a bare disconnect (so a dropped
    connection can still reconnect) and never over an in-flight "ending"
    (a POST .../end call owns that transition).
    """
    update: dict = {"last_sequence": sequence}
    if graceful_end and current_status == "created":
        update["status"] = "abandoned"
        update["ended_at"] = datetime.now(timezone.utc)
    return update


def _build_session_context(
    tp: dict | None,
    participant_personalities: dict[str, str],
) -> str:
    """Build the initial context message sent to the agent before conversation starts.

    Includes active personas (with their personalities) and topic pack content
    (if the pack is ready). The agent reads this silently — it must not be
    spoken aloud or acknowledged (per ROOT_INSTRUCTION rule 7).
    """
    lines = ["=== SESSION BRIEFING ==="]

    # Persona section
    if participant_personalities:
        lines.append("Active characters in this session (you play ALL of them):")
        for name, personality in participant_personalities.items():
            lines.append(f"  {name.capitalize()}: {personality}")
        lines.append(
            "Only speak as the listed characters above. "
            "Label every turn with the character's name followed by a colon."
        )

    # Topic section
    if tp and tp.get("status") == "ready":
        lines.append(f"\nTopic overview: {tp.get('overview', '(no overview)')}")
        if facts := tp.get("verified_facts"):
            lines.append("Facts you can state confidently:")
            lines.extend(f"  - {f}" for f in facts)
        if axes := tp.get("discussion_axes"):
            lines.append("Good conversation angles:")
            lines.extend(f"  - {a}" for a in axes)
        hooks = tp.get("persona_hooks", {})
        if isinstance(hooks, dict):
            for name, angle in hooks.items():
                if angle and name.lower() in participant_personalities:
                    lines.append(f"  {name.capitalize()}'s angle: {angle}")
        if beats := tp.get("conversation_beats"):
            lines.append("Suggested conversation flow:")
            lines.extend(f"  {i + 1}. {b}" for i, b in enumerate(beats))

    lines.append("\n=== END BRIEFING === Wait for the user to speak before starting.")
    return "\n".join(lines)


async def _inject_reconnect_history(
    agent_session: AgentLiveSession,
    session_id: str,
) -> None:
    """Send the last N session messages to the agent so it can continue naturally
    after a reconnect. Called only when last_sequence > 0."""
    recent = (
        firestore_client.get_client()
        .collection(SESSION_MESSAGES_COLLECTION)
        .where("session_id", "==", session_id)
        .order_by("created_at")
        .limit_to_last(_RECONNECT_HISTORY_LIMIT)
        .stream()
    )
    msgs = [d.to_dict() for d in recent]
    if not msgs:
        return
    lines = ["=== CONVERSATION HISTORY (reconnected — do NOT read aloud) ==="]
    for m in msgs:
        speaker = m.get("speaker_id", "user").capitalize()
        text = m.get("transcript", "")
        lines.append(f"{speaker}: {text}")
    lines.append("=== Continue naturally from where the conversation left off. ===")
    await agent_session.send_text("\n".join(lines))


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

    if doc.get("status") in ("completed", "ending", "abandoned"):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    agent_session = AgentLiveSession(doc["agent_session_id"])
    await agent_session.connect(user_id=session_id)

    # Persona + topic context injection (also used on reconnect)
    participant_personalities: dict[str, str] = doc.get("participant_personalities") or {}
    topic_pack_id = doc.get("topic_pack_id")
    tp = firestore_client.get_document(TOPIC_PACKS_COLLECTION, topic_pack_id) if topic_pack_id else None
    await agent_session.send_text(_build_session_context(tp, participant_personalities))

    # Reconnection: restore agent context from conversation history
    last_sequence: int = doc.get("last_sequence", 0)
    if last_sequence > 0:
        await _inject_reconnect_history(agent_session, session_id)

    settings = get_settings()
    max_secs = settings.session_max_duration_seconds
    warn_secs = int(max_secs * 0.8)

    sequence = last_sequence  # resume from where we left off
    ai_consecutive_turns = 0
    session_over = asyncio.Event()  # set to terminate all tasks cleanly
    # Set only on intentional-end paths (time limit / client request / rate
    # limit) -- NOT on bare disconnects, so a dropped connection can still
    # reconnect (see finally block below for why this distinction matters).
    graceful_end = False

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

    def _save_message(speaker_id: str, role: str, text: str, msg_status: str = "final") -> None:
        """Persist a confirmed utterance to session_messages (BUG-001/003 fix)."""
        firestore_client.create_document(
            SESSION_MESSAGES_COLLECTION,
            uuid.uuid4().hex,
            {
                "session_id": session_id,
                "speaker_id": speaker_id,
                "role": role,
                "transcript": text,
                "status": msg_status,
                "created_at": datetime.now(timezone.utc),
            },
        )

    # ------------------------------------------------------------------
    # Concurrent tasks
    # ------------------------------------------------------------------

    async def upstream() -> None:
        """Read WebSocket frames and forward to the agent."""
        nonlocal graceful_end
        msg_count = 0
        window_start = asyncio.get_event_loop().time()

        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return

            # Per-minute message rate limit
            now = asyncio.get_event_loop().time()
            if now - window_start >= 60:
                msg_count = 0
                window_start = now
            msg_count += 1
            if msg_count > _MAX_MSGS_PER_MIN:
                logger.warning("ws.rate_limit session_id=%s", session_id)
                await send_event("system.error", message="message rate limit exceeded")
                graceful_end = True
                session_over.set()
                return

            audio_bytes = message.get("bytes")
            if audio_bytes is not None:
                await agent_session.send_audio(audio_bytes)
                continue
            text_frame = message.get("text")
            if text_frame is not None:
                await _handle_client_event(json.loads(text_frame))

    async def downstream() -> None:
        """Read ADK events and forward to the WebSocket client."""
        nonlocal ai_consecutive_turns
        async for event in agent_session.events():
            if session_over.is_set():
                return

            if event.type == "audio_chunk" and event.audio is not None:
                await websocket.send_bytes(event.audio)

            elif event.type == "text_delta" and event.text:
                await send_event(
                    "agent.text.delta",
                    speaker_id=event.speaker_id,
                    text=event.text,
                )
                firestore_client.create_document(
                    DISPLAY_EVENTS_COLLECTION,
                    uuid.uuid4().hex,
                    {
                        "session_id": session_id,
                        "speaker_id": event.speaker_id,
                        "text": event.text,
                        "created_at": datetime.now(timezone.utc),
                    },
                )

            elif event.type == "text_final" and event.text:
                await send_event(
                    "agent.text.final",
                    speaker_id=event.speaker_id,
                    text=event.text,
                )
                _save_message(
                    speaker_id=event.speaker_id or "assistant",
                    role="assistant",
                    text=event.text,
                )

            elif event.type == "input_transcript_final" and event.text:
                ai_consecutive_turns = 0  # user spoke — reset floor counter
                await send_event("user.transcript.final", text=event.text)
                _save_message(speaker_id="user", role="user", text=event.text)

            elif event.type == "turn_complete":
                ai_consecutive_turns += 1
                await send_event("turn.complete", speaker_id=event.speaker_id)
                # Turn Controller: if AI has talked too many times without user,
                # open the floor and nudge the agent to stop.
                if ai_consecutive_turns >= _MAX_AI_CONSECUTIVE_TURNS:
                    ai_consecutive_turns = 0
                    await send_event("floor.opened")
                    await agent_session.send_text(_FLOOR_YIELD_NUDGE)

            elif event.type == "interrupted":
                ai_consecutive_turns = 0
                await send_event("agent.interrupted", speaker_id=event.speaker_id)

    async def session_timer() -> None:
        """Send time_warning at 80% mark; set session_over at the limit."""
        nonlocal graceful_end
        await asyncio.sleep(warn_secs)
        try:
            await send_event(
                "session.time_warning",
                remaining_seconds=max_secs - warn_secs,
            )
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(max_secs - warn_secs)
        try:
            await send_event("session.time_limit")
        except Exception:  # noqa: BLE001
            pass
        graceful_end = True
        session_over.set()

    async def ender() -> None:
        """Wait for session_over then raise to cancel all sibling tasks."""
        await session_over.wait()
        raise _SessionOver()

    async def _handle_client_event(data: dict) -> None:
        nonlocal graceful_end
        event_type = data.get("type")

        if event_type == "ping":
            await send_event("pong")

        elif event_type == "user.speech.start":
            await agent_session.send_activity_start()

        elif event_type == "user.speech.end":
            await agent_session.send_activity_end()

        elif event_type == "user.interrupt":
            await agent_session.send_interrupt()

        elif event_type == "user.text":
            text = data.get("payload", {}).get("text", "")
            if text:
                await agent_session.send_text(text)
                _save_message(speaker_id="user", role="user", text=text)

        elif event_type == "session.end.request":
            # Client requested graceful end — let ender() clean up
            await send_event("session.ending")
            graceful_end = True
            session_over.set()

        elif event_type == "client.resume":
            # Client explicitly requests resume after detecting a gap in sequences.
            # We already injected history in connect(); just acknowledge.
            await send_event("session.resumed", last_sequence=sequence)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    try:
        await send_event(
            "session.ready",
            reconnected=last_sequence > 0,
            last_sequence=last_sequence,
        )
        async with asyncio.TaskGroup() as tg:
            tg.create_task(upstream())
            tg.create_task(downstream())
            tg.create_task(session_timer())
            tg.create_task(ender())
    except* _SessionOver:
        pass
    except* WebSocketDisconnect:
        pass
    except* Exception as eg:
        for exc in eg.exceptions:
            logger.exception("ws.stream_error session_id=%s", session_id, exc_info=exc)
        try:
            await send_event("system.error", message="conversation stream failed")
        except Exception:  # noqa: BLE001
            pass
    finally:
        await agent_session.close()
        # Persist last_sequence so reconnects can resume from here.
        # Skip if session is already in terminal state (completed/ending).
        try:
            current = firestore_client.get_document(SESSIONS_COLLECTION, session_id)
            if current and current.get("status") not in ("completed", "ending"):
                update = _finalize_session_update(current.get("status"), graceful_end, sequence)
                firestore_client.update_document(SESSIONS_COLLECTION, session_id, update)
        except Exception:  # noqa: BLE001
            pass
