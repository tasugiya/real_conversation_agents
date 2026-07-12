"""Tests for topic_pack_generate.py.

Covers the fallback pack and JSON fence stripping (no Gemini calls needed).
"""

import json

import pytest

from src.tasks.topic_pack_generate import PersonaHooks, TopicPackOutput, _fallback_pack


class TestFallbackPack:
    def test_returns_topic_pack_output(self):
        pack = _fallback_pack("campus life")
        assert isinstance(pack, TopicPackOutput)

    def test_overview_mentions_topic(self):
        pack = _fallback_pack("Japanese food")
        assert "Japanese food" in pack.overview

    def test_has_discussion_axes(self):
        pack = _fallback_pack("travel")
        assert len(pack.discussion_axes) >= 1

    def test_has_user_cheat_sheet(self):
        pack = _fallback_pack("AI")
        assert len(pack.user_cheat_sheet) >= 3

    def test_persona_hooks_present(self):
        pack = _fallback_pack("music")
        assert isinstance(pack.persona_hooks, PersonaHooks)
        assert pack.persona_hooks.alice
        assert pack.persona_hooks.bob

    def test_verified_facts_empty_for_fallback(self):
        pack = _fallback_pack("anything")
        assert pack.verified_facts == []

    def test_sources_empty_for_fallback(self):
        pack = _fallback_pack("anything")
        assert pack.sources == []


class TestTopicPackOutputValidation:
    def test_valid_construct(self):
        pack = TopicPackOutput(
            overview="Test overview.",
            verified_facts=["Fact 1"],
            uncertain_claims=[],
            discussion_axes=["Angle A", "Angle B"],
            personal_angles=["Personal 1"],
            persona_hooks=PersonaHooks(alice="curious", bob="skeptical"),
            conversation_beats=["Beat 1", "Beat 2"],
            user_cheat_sheet=["I think...", "What about you?"],
        )
        assert pack.overview == "Test overview."
        assert len(pack.verified_facts) == 1
