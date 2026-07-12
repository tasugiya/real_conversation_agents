"""Local ADK runner for the live conversation (PoC / Phase-1).

Phase 1 (current): InMemorySessionService — validates that Cloud Run + ADK +
Gemini Live API can exchange audio/text end-to-end. Session state is
in-process only; Firestore remains the SoT for conversation logs and reviews.
Known limitation: sessions are not shared across Cloud Run instances (single
instance PoC is fine, scale via Cloud Run min-instances=1 for demo).

Phase 2 (future): Replace InMemorySessionService with VertexAiSessionService
so sessions survive restarts and scale across instances.

Why not Agent Engine bidi streaming (original approach):
  vertexai 1.160.0 / google-genai 2.11.0 — _wrap_bidi_stream_query_operation
  raises NotImplementedError; client.aio.live.agent_engines does not exist yet
  in the installed genai SDK. See TODO.md BUG-002.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import vertexai
from google.adk.agents import Agent
from google.adk.agents.live_request_queue import LiveRequest, LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ..config import get_settings

MODEL_NAME = "gemini-live-2.5-flash-native-audio"

_APP_NAME = "real-conv"

ROOT_INSTRUCTION = """
You are running a small group English conversation practice session with a
human user. You play two AI characters yourself:

- Alice: warm, casual, asks a lot of follow-up questions.
- Bob: a bit more skeptical, offers gentle counterpoints, calm tone.

Rules:
1. Only one character speaks per turn. Never speak as both in the same turn.
2. Start every spoken turn with the character's name and a colon, for
   example "Alice: That's interesting, what do you think?". Always include
   this even when speaking aloud -- the application uses it to identify the
   current speaker.
3. Never speak while the user is still talking.
4. After the user finishes speaking, wait briefly, then have exactly one
   character respond. Occasionally let the other character add one short
   remark, but do not have both characters talk back-to-back more than once
   before returning the floor to the user.
5. Ask the user a question at least every few turns so they stay involved.
6. Keep each turn short: one to three sentences.
7. If you receive a message starting with "=== CONVERSATION TOPIC CONTEXT ===",
   read it silently as your briefing — do NOT read it aloud or acknowledge it.
   Use the topic, facts, and conversation beats to guide the discussion naturally.
8. Only state something as a fact if it appears in your topic context briefing;
   for everything else, frame it as an opinion ("I think...", "I heard that...").
9. Speak in English at a level a language learner can follow (B1-B2 level).
"""

# ---------------------------------------------------------------------------
# Normalized event type
# ---------------------------------------------------------------------------

@dataclass
class AgentEvent:
    """Normalized event yielded to routes/ws.py, independent of ADK internals."""

    type: str
    # "text_delta" | "text_final" | "audio_chunk" | "turn_complete"
    # | "interrupted" | "input_transcript_final"
    speaker_id: str | None = None
    text: str | None = None
    audio: bytes | None = None


# ---------------------------------------------------------------------------
# Singleton runner
# ---------------------------------------------------------------------------

_session_service = InMemorySessionService()
_runner: Runner | None = None


def _get_runner() -> Runner:
    global _runner
    if _runner is None:
        settings = get_settings()
        # Tell google-genai SDK to use Vertex AI backend (IAM/ADC) instead of
        # Google AI Studio (which requires an API key). Must be called before
        # the ADK Agent/Runner is instantiated.
        vertexai.init(project=settings.gcp_project_id, location=settings.gcp_region)
        agent = Agent(
            name="conversation_agent",
            model=MODEL_NAME,
            instruction=ROOT_INSTRUCTION,
        )
        _runner = Runner(
            app_name=_APP_NAME,
            agent=agent,
            session_service=_session_service,
        )
    return _runner


# ---------------------------------------------------------------------------
# Public API (same interface as before so routes/ws.py needs minimal changes)
# ---------------------------------------------------------------------------

async def create_agent_session(user_id: str) -> str:
    """Create an ADK session and return its ID."""
    runner = _get_runner()
    session = await runner.session_service.create_session(
        app_name=_APP_NAME,
        user_id=user_id,
    )
    return session.id if hasattr(session, "id") else str(session)


class AgentLiveSession:
    """One instance per WebSocket connection / conversation session.

    The caller (ws.py) must call connect(user_id=...) before events() or any
    send_* method.
    """

    def __init__(self, agent_session_id: str) -> None:
        self._agent_session_id = agent_session_id
        self._user_id: str = agent_session_id
        self._queue: LiveRequestQueue | None = None

    async def connect(self, user_id: str | None = None) -> None:
        self._user_id = user_id or self._agent_session_id
        self._queue = LiveRequestQueue()

    # ------------------------------------------------------------------
    # Send helpers
    # ------------------------------------------------------------------

    def _send(self, request: LiveRequest) -> None:
        if self._queue is None:
            raise RuntimeError("AgentLiveSession.connect() not called")
        self._queue.send(request)

    async def send_audio(self, chunk: bytes) -> None:
        self._send(LiveRequest(blob=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")))

    async def send_text(self, text: str) -> None:
        self._send(LiveRequest(
            content=types.Content(role="user", parts=[types.Part(text=text)])
        ))

    async def send_activity_start(self) -> None:
        """Signal push-to-talk start (user begins speaking)."""
        self._send(LiveRequest(activity_start=types.ActivityStart()))

    async def send_activity_end(self) -> None:
        """Signal push-to-talk end (user finished speaking)."""
        self._send(LiveRequest(activity_end=types.ActivityEnd()))

    async def send_interrupt(self) -> None:
        """Interrupt AI speech by signalling new user activity."""
        self._send(LiveRequest(activity_start=types.ActivityStart()))

    # ------------------------------------------------------------------
    # Event stream
    # ------------------------------------------------------------------

    async def events(self) -> AsyncIterator[AgentEvent]:
        runner = _get_runner()
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=[types.Modality.AUDIO, types.Modality.TEXT],
        )
        # Stateful speaker tracking: "Alice:" label only appears in the first
        # delta of a turn; subsequent deltas must inherit it (BUG-005 fix).
        current_speaker: str | None = None
        async for raw_event in runner.run_live(
            user_id=self._user_id,
            session_id=self._agent_session_id,
            live_request_queue=self._queue,
            run_config=run_config,
        ):
            for evt in _normalize_event(raw_event, current_speaker):
                # Update carry-over speaker from the first delta that has one
                if evt.type in ("text_delta", "audio_chunk") and evt.speaker_id:
                    current_speaker = evt.speaker_id
                elif evt.type == "turn_complete":
                    current_speaker = None
                yield evt

    async def close(self) -> None:
        if self._queue is not None:
            self._queue.close()
            self._queue = None


# ---------------------------------------------------------------------------
# Event normalizer
# ---------------------------------------------------------------------------

_KNOWN_PERSONAS = frozenset(("alice", "bob"))


def _extract_speaker_from_text(text: str) -> tuple[str | None, str]:
    """Try to pull 'Alice:' / 'Bob:' prefix from the first line."""
    first_line = text.split("\n", 1)[0]
    if ":" not in first_line:
        return None, text
    label, _, rest = text.partition(":")
    if label.strip().lower() in _KNOWN_PERSONAS:
        return label.strip().lower(), rest.strip()
    return None, text


def _normalize_event(raw: Event, current_speaker: str | None = None) -> list[AgentEvent]:
    """Convert one ADK Event to zero or more AgentEvents.

    current_speaker carries the last known persona name across delta calls so
    that fragments without a leading "Alice:" / "Bob:" label are still attributed
    correctly (BUG-005 fix).
    """
    results: list[AgentEvent] = []

    if raw.content and raw.content.parts:
        for part in raw.content.parts:
            if part.inline_data and part.inline_data.data:
                results.append(AgentEvent(
                    type="audio_chunk",
                    speaker_id=current_speaker or raw.author or None,
                    audio=part.inline_data.data,
                ))
            elif part.text:
                speaker_id, text = _extract_speaker_from_text(part.text)
                results.append(AgentEvent(
                    type="text_delta",
                    speaker_id=speaker_id or current_speaker or raw.author or None,
                    text=text,
                ))

    # AI speech transcription (output_transcription.finished == True for final)
    if raw.output_transcription and raw.output_transcription.text:
        if raw.output_transcription.finished:
            speaker_id, text = _extract_speaker_from_text(raw.output_transcription.text)
            results.append(AgentEvent(
                type="text_final",
                speaker_id=speaker_id or current_speaker or raw.author or None,
                text=text,
            ))

    # User speech transcription
    if raw.input_transcription and raw.input_transcription.text:
        if raw.input_transcription.finished:
            results.append(AgentEvent(
                type="input_transcript_final",
                speaker_id="user",
                text=raw.input_transcription.text,
            ))

    if raw.turn_complete:
        results.append(AgentEvent(type="turn_complete", speaker_id=raw.author or None))

    if raw.interrupted:
        results.append(AgentEvent(type="interrupted", speaker_id=raw.author or None))

    return results
