"""Tests for ws.py helper functions.

Pure logic functions that need no external services:
  - _build_session_context: formats topic pack + persona into agent briefing
"""

import pytest

from src.routes.ws import _build_session_context


class TestBuildSessionContext:
    def _make_tp(self, **overrides):
        base = {
            "status": "ready",
            "overview": "A conversation about AI in daily life.",
            "verified_facts": ["AI assistants can set reminders.", "LLMs use transformers."],
            "discussion_axes": ["How do you use AI at home?", "Is AI replacing jobs?"],
            "persona_hooks": {
                "alice": "excited about productivity tools",
                "bob": "worried about privacy implications",
            },
            "conversation_beats": ["Introduce the topic", "Ask the user", "React"],
        }
        base.update(overrides)
        return base

    def test_includes_overview(self):
        tp = self._make_tp()
        result = _build_session_context(tp, {"alice": "warm and curious"})
        assert "AI in daily life" in result

    def test_includes_verified_facts(self):
        tp = self._make_tp()
        result = _build_session_context(tp, {"alice": "warm"})
        assert "AI assistants can set reminders" in result

    def test_includes_discussion_axes(self):
        tp = self._make_tp()
        result = _build_session_context(tp, {"alice": "warm"})
        assert "How do you use AI at home?" in result

    def test_includes_persona_personalities(self):
        result = _build_session_context(
            None, {"alice": "warm and curious", "bob": "slightly skeptical"}
        )
        assert "Alice" in result
        assert "warm and curious" in result
        assert "Bob" in result
        assert "slightly skeptical" in result

    def test_topic_hook_only_shown_for_active_persona(self):
        """persona_hooks for inactive personas should not appear."""
        tp = self._make_tp()
        # Only alice is active
        result = _build_session_context(tp, {"alice": "warm"})
        assert "excited about productivity tools" in result
        # bob hook should NOT appear since bob is not active
        assert "worried about privacy implications" not in result

    def test_pending_topic_pack_not_injected(self):
        tp = self._make_tp(status="pending")
        result = _build_session_context(tp, {"alice": "warm"})
        # Overview should NOT appear for pending packs
        assert "AI in daily life" not in result

    def test_none_topic_pack_still_includes_personas(self):
        result = _build_session_context(None, {"emma": "energetic"})
        assert "Emma" in result
        assert "energetic" in result

    def test_empty_participants_still_includes_topic(self):
        tp = self._make_tp()
        result = _build_session_context(tp, {})
        assert "AI in daily life" in result

    def test_starts_with_briefing_header(self):
        result = _build_session_context(None, {})
        assert result.startswith("=== SESSION BRIEFING ===")

    def test_fresh_session_ends_with_opening_instruction(self):
        # The characters open the conversation themselves (P2 redesign) --
        # the user should not have to speak first.
        result = _build_session_context(None, {})
        assert "Open the conversation now" in result
        assert "do not greet the user again" not in result

    def test_reconnected_session_does_not_greet_again(self):
        result = _build_session_context(None, {}, reconnected=True)
        assert "do not greet the user again" in result
        assert "Open the conversation now" not in result

    def test_conversation_beats_numbered(self):
        tp = self._make_tp()
        result = _build_session_context(tp, {})
        assert "1. Introduce the topic" in result
        assert "2. Ask the user" in result

    def test_defaults_to_english(self):
        result = _build_session_context(None, {})
        assert "Conversation language: English" in result

    def test_japanese_language_injected(self):
        # Regression guard: CreateSessionRequest.language was accepted but
        # never persisted or used -- ws.py always spoke English regardless
        # of the user's selection.
        result = _build_session_context(None, {}, language="ja")
        assert "Conversation language: Japanese" in result
        assert "English" not in result

    def test_unknown_language_code_falls_back_to_english(self):
        result = _build_session_context(None, {}, language="fr")
        assert "Conversation language: English" in result
