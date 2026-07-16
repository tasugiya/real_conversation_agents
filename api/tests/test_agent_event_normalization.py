"""Tests for agent_engine_client speaker extraction and event normalization.

These tests cover pure logic functions that require no external services:
  - _extract_speaker_from_text: parses "Alice: ..." labels
  - _normalize_event: converts ADK Event to AgentEvent list
  - AgentLiveSession.events() speaker carry-over (BUG-005 fix)
"""

from unittest.mock import MagicMock

import pytest

from src.services.agent_engine_client import (
    AgentEvent,
    _KNOWN_PERSONAS,
    _extract_speaker_from_text,
    _normalize_event,
    _split_speaker_segments,
)


# ---------------------------------------------------------------------------
# _extract_speaker_from_text
# ---------------------------------------------------------------------------

class TestExtractSpeakerFromText:
    def test_alice_label(self):
        speaker, text = _extract_speaker_from_text("Alice: That's interesting!")
        assert speaker == "alice"
        assert text == "That's interesting!"

    def test_bob_label(self):
        speaker, text = _extract_speaker_from_text("Bob: I'm not so sure about that.")
        assert speaker == "bob"
        assert text == "I'm not so sure about that."

    def test_capitalisation_insensitive(self):
        speaker, text = _extract_speaker_from_text("ALICE: hello")
        assert speaker == "alice"

    def test_no_label_returns_none(self):
        speaker, text = _extract_speaker_from_text("Just a plain sentence.")
        assert speaker is None
        assert text == "Just a plain sentence."

    def test_unknown_name_before_colon(self):
        # "Charlie:" is not a known persona
        speaker, text = _extract_speaker_from_text("Charlie: Who am I?")
        assert speaker is None
        # text is returned unchanged because the label was not recognized
        assert "Charlie" in text

    @pytest.mark.parametrize("name", ["Emma", "David", "Mia"])
    def test_full_persona_pool_recognized(self, name):
        # Regression guard for BUG-019: _KNOWN_PERSONAS previously hardcoded
        # only alice/bob, so any session where select_personas() picked a
        # different pair (e.g. emma/david) always fell through to
        # raw.author ("conversation_agent") even when the model correctly
        # labeled its turn.
        speaker, text = _extract_speaker_from_text(f"{name}: Nice to meet you.")
        assert speaker == name.lower()
        assert text == "Nice to meet you."

    def test_known_personas_matches_full_pool(self):
        assert _KNOWN_PERSONAS == {"alice", "bob", "emma", "david", "mia"}

    def test_colon_in_middle_of_sentence(self):
        # Colon is not at a persona label position
        speaker, text = _extract_speaker_from_text("Here is a list: items")
        # "Here is a list" is not in KNOWN_PERSONAS
        assert speaker is None

    def test_empty_string(self):
        speaker, text = _extract_speaker_from_text("")
        assert speaker is None
        assert text == ""

    def test_only_label_no_text(self):
        speaker, text = _extract_speaker_from_text("Alice:")
        assert speaker == "alice"
        assert text == ""


# ---------------------------------------------------------------------------
# _split_speaker_segments (BUG-031: one turn containing several characters)
# ---------------------------------------------------------------------------

class TestSplitSpeakerSegments:
    def test_single_labelled_segment(self):
        assert _split_speaker_segments("Alice: Hello there!") == [("alice", "Hello there!")]

    def test_no_label(self):
        assert _split_speaker_segments("just plain text") == [(None, "just plain text")]

    def test_empty_text(self):
        assert _split_speaker_segments("   ") == []

    def test_two_speakers_in_one_turn(self):
        segments = _split_speaker_segments("Mia: I love that show. Emma: 本当ですね！")
        assert segments == [("mia", "I love that show."), ("emma", "本当ですね！")]

    def test_second_label_on_new_line(self):
        segments = _split_speaker_segments("Mia: First thought.\nEmma: Second thought.")
        assert segments == [("mia", "First thought."), ("emma", "Second thought.")]

    def test_leading_unlabelled_text_kept_with_none_speaker(self):
        segments = _split_speaker_segments("...continuing. Bob: My turn now.")
        assert segments == [(None, "...continuing."), ("bob", "My turn now.")]

    def test_unknown_name_not_split(self):
        assert _split_speaker_segments("Charlie: Who am I?") == [(None, "Charlie: Who am I?")]

    def test_mid_word_colon_not_split(self):
        # "Here is a list:" — no persona label, no split
        assert _split_speaker_segments("Here is a list: items") == [(None, "Here is a list: items")]

    def test_label_only_fragment_keeps_speaker(self):
        # A streaming delta that is exactly the label must keep attribution
        assert _split_speaker_segments("Alice:") == [("alice", "")]

    def test_case_insensitive(self):
        assert _split_speaker_segments("EMMA: hi")[0][0] == "emma"


# ---------------------------------------------------------------------------
# _normalize_event
# ---------------------------------------------------------------------------

def _make_raw_event(**kwargs) -> MagicMock:
    """Create a minimal ADK Event mock."""
    raw = MagicMock()
    raw.content = None
    raw.author = None
    raw.output_transcription = None
    raw.input_transcription = None
    raw.turn_complete = False
    raw.interrupted = False
    for k, v in kwargs.items():
        setattr(raw, k, v)
    return raw


def _make_part(text=None, audio=None):
    part = MagicMock()
    part.text = text
    if audio is not None:
        part.inline_data = MagicMock()
        part.inline_data.data = audio
    else:
        part.inline_data = None
    return part


class TestNormalizeEvent:
    def test_audio_chunk_event(self):
        audio_bytes = b"\x00\x01\x02"
        raw = _make_raw_event(author="conversation_agent")
        raw.content = MagicMock()
        raw.content.parts = [_make_part(audio=audio_bytes)]

        results = _normalize_event(raw)
        assert len(results) == 1
        evt = results[0]
        assert evt.type == "audio_chunk"
        assert evt.audio == audio_bytes

    def test_text_delta_without_label(self):
        raw = _make_raw_event(author="conversation_agent")
        raw.content = MagicMock()
        raw.content.parts = [_make_part(text="and she said")]

        results = _normalize_event(raw, current_speaker="alice")
        assert len(results) == 1
        evt = results[0]
        assert evt.type == "text_delta"
        assert evt.speaker_id == "alice"  # carried over
        assert evt.text == "and she said"

    def test_text_delta_with_label_sets_speaker(self):
        raw = _make_raw_event()
        raw.content = MagicMock()
        raw.content.parts = [_make_part(text="Alice: Let me tell you")]

        results = _normalize_event(raw)
        assert results[0].speaker_id == "alice"
        assert results[0].text == "Let me tell you"

    def test_output_transcription_final(self):
        raw = _make_raw_event()
        transcription = MagicMock()
        transcription.text = "Bob: I disagree with that."
        transcription.finished = True
        raw.output_transcription = transcription

        results = _normalize_event(raw)
        finals = [r for r in results if r.type == "text_final"]
        assert len(finals) == 1
        assert finals[0].speaker_id == "bob"
        assert finals[0].text == "I disagree with that."

    def test_output_transcription_with_two_speakers_is_split(self):
        # BUG-031: a turn violating rule 1 must become one event per speaker
        raw = _make_raw_event()
        transcription = MagicMock()
        transcription.text = "Mia: That was fun. Emma: 本当ですね！"
        transcription.finished = True
        raw.output_transcription = transcription

        results = _normalize_event(raw)
        finals = [r for r in results if r.type == "text_final"]
        assert [(f.speaker_id, f.text) for f in finals] == [
            ("mia", "That was fun."),
            ("emma", "本当ですね！"),
        ]

    def test_text_delta_with_two_speakers_is_split(self):
        raw = _make_raw_event()
        raw.content = MagicMock()
        raw.content.parts = [_make_part(text="Alice: Hi! Bob: Hello!")]

        results = _normalize_event(raw)
        assert [(r.speaker_id, r.text) for r in results] == [
            ("alice", "Hi!"),
            ("bob", "Hello!"),
        ]

    def test_wrap_up_tool_call_emits_session_wrap(self):
        # ROOT_INSTRUCTION rule 12: the model calls wrap_up_session after the
        # goodbye turn; ws.py ends the session gracefully on this event.
        function_call = MagicMock()
        function_call.name = "wrap_up_session"
        part = MagicMock()
        part.text = None
        part.inline_data = None
        part.function_call = function_call
        raw = _make_raw_event()
        raw.content = MagicMock()
        raw.content.parts = [part]

        results = _normalize_event(raw)
        assert [r.type for r in results] == ["session_wrap"]

    def test_other_tool_calls_are_ignored(self):
        function_call = MagicMock()
        function_call.name = "some_other_tool"
        part = MagicMock()
        part.text = None
        part.inline_data = None
        part.function_call = function_call
        raw = _make_raw_event()
        raw.content = MagicMock()
        raw.content.parts = [part]

        assert _normalize_event(raw) == []

    def test_output_transcription_not_final_is_ignored(self):
        raw = _make_raw_event()
        transcription = MagicMock()
        transcription.text = "partial text"
        transcription.finished = False
        raw.output_transcription = transcription

        results = _normalize_event(raw)
        assert not any(r.type == "text_final" for r in results)

    def test_input_transcription_final(self):
        raw = _make_raw_event()
        transcription = MagicMock()
        transcription.text = "What do you think?"
        transcription.finished = True
        raw.input_transcription = transcription

        results = _normalize_event(raw)
        user_finals = [r for r in results if r.type == "input_transcript_final"]
        assert len(user_finals) == 1
        assert user_finals[0].speaker_id == "user"
        assert user_finals[0].text == "What do you think?"

    def test_turn_complete_event(self):
        raw = _make_raw_event(turn_complete=True, author="conversation_agent")
        results = _normalize_event(raw)
        assert any(r.type == "turn_complete" for r in results)

    def test_interrupted_event(self):
        raw = _make_raw_event(interrupted=True)
        results = _normalize_event(raw)
        assert any(r.type == "interrupted" for r in results)

    def test_empty_event_returns_empty(self):
        raw = _make_raw_event()
        results = _normalize_event(raw)
        assert results == []

    def test_multiple_parts(self):
        raw = _make_raw_event()
        raw.content = MagicMock()
        raw.content.parts = [
            _make_part(text="Alice: Hello"),
            _make_part(audio=b"\xff"),
        ]
        results = _normalize_event(raw)
        assert len(results) == 2
        assert results[0].type == "text_delta"
        assert results[1].type == "audio_chunk"
