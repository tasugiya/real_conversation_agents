"""Local ADK runner for the live conversation.

Session storage: VertexAiSessionService, backed by the Vertex AI Agent
Engine Sessions API against the existing AGENT_ENGINE_RESOURCE_NAME
reasoningEngine resource. Replaced InMemorySessionService (used until
2026-07-12) after it caused unbounded memory growth in Cloud Run --
delete_session() was never called anywhere, so every created session and
its full event history (including audio) lived in process memory forever.
InMemorySessionService also can't be shared across Cloud Run instances
(sessionAffinity is off here), so a reconnect landing on a different
instance would silently lose the session. VertexAiSessionService persists
server-side and fixes both. Firestore remains the SoT for conversation
logs and reviews; this is only ADK's own turn/state bookkeeping.

LLM execution / audio streaming still runs locally in this process via
Runner.run_live() -- only session *storage* moved to Vertex AI. This is
unrelated to Agent Engine's bidi-streaming *compute* path (deploying the
agent itself to run on Agent Engine), which remains abandoned:
  vertexai 1.160.0 / google-genai 2.11.0 — _wrap_bidi_stream_query_operation
  raises NotImplementedError; client.aio.live.agent_engines does not exist yet
  in the installed genai SDK. See TODO.md BUG-002.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from google.adk.agents import Agent
from google.adk.agents.live_request_queue import LiveRequest, LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import VertexAiSessionService
from google.genai import types

from ..config import get_settings
from .personas import PERSONA_POOL

MODEL_NAME = "gemini-live-2.5-flash-native-audio"

_APP_NAME = "real-conv"

# Server-side storage TTL for Vertex AI sessions -- a cleanup safety net,
# deliberately decoupled from session_max_duration_seconds (which controls
# conversation length, not how long the storage record should live).
# 24h is the platform minimum (Vertex AI rejects anything shorter with
# INVALID_ARGUMENT: "ttl must be at least 24 hours" -- confirmed against the
# real API); it also matches this codebase's existing 24h TTL convention for
# Firestore records (firestore_client.py's TTL_HOURS).
_SESSION_TTL = "86400s"


def _extract_reasoning_engine_id(resource_name: str) -> str:
    """'projects/P/locations/L/reasoningEngines/123' -> '123'.

    VertexAiSessionService's agent_engine_id is used verbatim (unvalidated)
    to build the API path, so passing the full resource name here would
    produce a malformed URL -- it must be just the trailing numeric id.
    """
    return resource_name.rsplit("/", 1)[-1]


ROOT_INSTRUCTION = """
You are running a small group English conversation practice session with a
human user. You play the AI characters listed in the SESSION BRIEFING below.

Make it feel like a real group of friends chatting: the characters keep a
lively discussion going among themselves, and the user is welcome to jump
in at any time.

Rules:
1. Only one character speaks per turn. Never speak as more than one
   character in the same turn, and never include another character's
   name-labelled line (like "Emma: ...") inside the current character's
   turn. If another character wants to react, end the turn and start a
   new turn as that character.
2. Start every spoken turn with the character's name and a colon, for
   example "Alice: That's interesting, what do you think?". Always include
   this even when speaking aloud -- the application uses it to identify the
   current speaker.
3. Never speak while the user is still talking.
4. When the user speaks, always react to what they said: exactly one
   character responds first. Between user turns, the characters keep
   discussing the topic among themselves -- agreeing, disagreeing, joking,
   and building on each other. They do NOT need to hand the floor back to
   the user after every turn.
5. Every few turns, naturally invite the user in (ask their opinion, or
   relate the topic to them). Never pressure them: if they stay quiet,
   simply continue the conversation among the characters.
6. Keep each turn short: one to three sentences.
7. Messages wrapped in "=== ... ===" markers (such as SESSION BRIEFING or
   CONVERSATION HISTORY) and messages starting with "[DIRECTOR NOTE]" are
   silent stage directions from the application, NOT something the user
   said. Read them silently and follow them in your next utterance. Never
   read them aloud, never mention them, and never acknowledge, thank, or
   apologise for them.
8. Only state something as a fact if it appears in your briefing; for
   everything else, frame it as an opinion ("I think...", "I heard that...").
9. Speak in the conversation language given in your SESSION BRIEFING (English
   by default) at a level a language learner can follow (B1-B2 level).
10. You do not know the user's name. Address the user directly as "you"
   (or the natural second-person form of the conversation language, e.g.
   "あなた" in Japanese). Never invent a name for the user and never use a
   placeholder like "〇〇さん".
11. Perform each character with the distinct voice style described in the
   SESSION BRIEFING (pitch, energy, pace) and keep it consistent for the
   whole session, so listeners can tell the characters apart by sound alone.
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

_runner: Runner | None = None


def _get_runner() -> Runner:
    global _runner
    if _runner is None:
        settings = get_settings()
        session_service = VertexAiSessionService(
            project=settings.gcp_project_id,
            location=settings.gcp_region,
            agent_engine_id=_extract_reasoning_engine_id(settings.agent_engine_resource_name),
        )
        # ADK builds its own google-genai Client internally (google_llm.py's
        # api_client/_live_api_client) and does NOT read vertexai.init()'s
        # global state -- that only affects the older vertexai.generative_models
        # SDK (used by gemini_client.py), a separate mechanism entirely. Without
        # an explicit vertexai=True/project/location, google-genai falls back to
        # the GOOGLE_GENAI_USE_VERTEXAI/GOOGLE_CLOUD_PROJECT/GOOGLE_CLOUD_LOCATION
        # env vars, which aren't set here, so it defaults to API-key mode and
        # fails with "No API key was provided". client_kwargs is ADK's supported
        # pass-through to the google.genai.Client constructor for exactly this.
        model = Gemini(
            model=MODEL_NAME,
            client_kwargs={
                "vertexai": True,
                "project": settings.gcp_project_id,
                "location": settings.gcp_region,
            },
        )
        agent = Agent(
            name="conversation_agent",
            model=model,
            instruction=ROOT_INSTRUCTION,
        )
        _runner = Runner(
            app_name=_APP_NAME,
            agent=agent,
            session_service=session_service,
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
        ttl=_SESSION_TTL,
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
            # The Live API setup request accepts at most one response
            # modality; requesting [AUDIO, TEXT] together is rejected with
            # close code 1007 ("At most one response modality can be
            # specified..."). output_audio_transcription is the documented
            # way to get a text transcript alongside AUDIO playback.
            response_modalities=[types.Modality.AUDIO],
            output_audio_transcription=types.AudioTranscriptionConfig(),
            # Without this, raw.input_transcription is never populated, so
            # input_transcript_final never fires and the user's spoken turns
            # never get saved to session_messages (BUG-024) -- Review
            # transcripts would only ever contain the AI's side.
            input_audio_transcription=types.AudioTranscriptionConfig(),
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
                # Update carry-over speaker from the first event that has one
                # (text_final included -- previously omitted, so a
                # successfully-labeled output_transcription never corrected
                # a bad guess made by an earlier audio_chunk in the same turn).
                if evt.type in ("text_delta", "audio_chunk", "text_final") and evt.speaker_id:
                    current_speaker = evt.speaker_id
                # Deliberately NOT reset on turn_complete: the next turn's
                # first audio_chunk arrives before its transcription is
                # available, so it would otherwise fall back to raw.author
                # ("conversation_agent", BUG-019) instead of at worst
                # showing the previous turn's speaker for a moment.
                yield evt

    async def close(self) -> None:
        if self._queue is not None:
            self._queue.close()
            self._queue = None


# ---------------------------------------------------------------------------
# Event normalizer
# ---------------------------------------------------------------------------

# Derived from the full pool, not hardcoded to alice/bob (BUG-019 fix):
# select_personas() can pick any subset of PERSONA_POOL per session, so a
# session with e.g. emma/david previously had no way for the model's
# correctly-labeled "Emma:" turns to be recognized here -- they always fell
# through to raw.author ("conversation_agent").
_KNOWN_PERSONAS = frozenset(p.name for p in PERSONA_POOL)


def _extract_speaker_from_text(text: str) -> tuple[str | None, str]:
    """Try to pull 'Alice:' / 'Bob:' prefix from the first line."""
    first_line = text.split("\n", 1)[0]
    if ":" not in first_line:
        return None, text
    label, _, rest = text.partition(":")
    if label.strip().lower() in _KNOWN_PERSONAS:
        return label.strip().lower(), rest.strip()
    return None, text


# Matches a known persona label ("Emma:", "  mia :") at the start of the text
# or right after whitespace/newline, so a single model turn that (against
# ROOT_INSTRUCTION rule 1) contains several characters can be split into one
# event per speaker (BUG-031).
_SPEAKER_LABEL_RE = re.compile(
    r"(?:^|(?<=\s))(" + "|".join(re.escape(name) for name in sorted(_KNOWN_PERSONAS)) + r")\s*:",
    re.IGNORECASE,
)


def _split_speaker_segments(text: str) -> list[tuple[str | None, str]]:
    """Split text into (speaker_id, text) segments on known 'Name:' labels.

    Text before the first label is returned with speaker None (the caller
    falls back to the carried-over current speaker). A labelled segment is
    kept even when its text is empty so the speaker attribution survives
    (e.g. a delta fragment that is exactly "Alice:").
    """
    matches = list(_SPEAKER_LABEL_RE.finditer(text))
    if not matches:
        return [(None, text.strip())] if text.strip() else []
    segments: list[tuple[str | None, str]] = []
    leading = text[: matches[0].start()].strip()
    if leading:
        segments.append((None, leading))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segments.append((match.group(1).lower(), text[match.end():end].strip()))
    return segments


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
                for speaker_id, text in _split_speaker_segments(part.text):
                    results.append(AgentEvent(
                        type="text_delta",
                        speaker_id=speaker_id or current_speaker or raw.author or None,
                        text=text,
                    ))
                    # Later segments in the same part must not fall back to
                    # the pre-part speaker once a labelled segment appeared.
                    if speaker_id:
                        current_speaker = speaker_id

    # AI speech transcription (output_transcription.finished == True for final)
    if raw.output_transcription and raw.output_transcription.text:
        if raw.output_transcription.finished:
            for speaker_id, text in _split_speaker_segments(raw.output_transcription.text):
                results.append(AgentEvent(
                    type="text_final",
                    speaker_id=speaker_id or current_speaker or raw.author or None,
                    text=text,
                ))
                if speaker_id:
                    current_speaker = speaker_id

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
