"""Tests for topic_pack_generate.py.

Covers the fallback pack, schema validation, and the two-stage pipeline
(parallel grounded research facets + non-grounded structured synthesis) --
no real Gemini calls needed, the client is always mocked.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.tasks.topic_pack_generate import (
    PersonaHooks,
    TopicPackOutput,
    _DEBATES_PROMPT_TEMPLATE,
    _fallback_pack,
    _format_research_notes,
    _research_facet,
    _run_research,
    _structure_pack,
)


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


class TestResearchFacet:
    def test_uses_grounding_tool_without_response_schema(self):
        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = MagicMock(text="research output")

        result = _research_facet(fake_client, "AI", "Research {topic} as of {today}", "2026-07-12")

        assert result == "research output"
        _, kwargs = fake_client.models.generate_content.call_args
        config = kwargs["config"]
        assert config.tools is not None
        assert config.response_schema is None
        assert config.response_mime_type is None

    def test_formats_prompt_with_topic_and_today(self):
        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = MagicMock(text="x")

        _research_facet(fake_client, "AI", "Topic: {topic}, Date: {today}", "2026-07-12")

        _, kwargs = fake_client.models.generate_content.call_args
        assert kwargs["contents"] == "Topic: AI, Date: 2026-07-12"

    def test_propagates_exception_to_caller(self):
        fake_client = MagicMock()
        fake_client.models.generate_content.side_effect = Exception("api error")

        with pytest.raises(Exception, match="api error"):
            _research_facet(fake_client, "AI", "{topic}", "2026-07-12")


class TestRunResearch:
    def test_all_facets_succeed(self):
        def fake_facet(client, topic, prompt_template, today):
            return f"notes for {topic}"

        with patch("src.tasks.topic_pack_generate._research_facet", side_effect=fake_facet):
            notes = _run_research(MagicMock(), "AI")

        assert set(notes.keys()) == {
            "facts_and_overview",
            "debates_and_uncertain_claims",
            "current_relevance",
        }
        assert all(v == "notes for AI" for v in notes.values())

    def test_one_facet_failure_gets_placeholder_others_preserved(self):
        def fake_facet(client, topic, prompt_template, today):
            if prompt_template == _DEBATES_PROMPT_TEMPLATE:
                raise Exception("boom")
            return "ok"

        with patch("src.tasks.topic_pack_generate._research_facet", side_effect=fake_facet):
            notes = _run_research(MagicMock(), "AI")

        assert notes["debates_and_uncertain_claims"] == "(no research results for this facet)"
        assert notes["facts_and_overview"] == "ok"
        assert notes["current_relevance"] == "ok"

    def test_returns_all_three_keys_in_definition_order(self):
        with patch("src.tasks.topic_pack_generate._research_facet", return_value="x"):
            notes = _run_research(MagicMock(), "AI")

        assert list(notes.keys()) == [
            "facts_and_overview",
            "debates_and_uncertain_claims",
            "current_relevance",
        ]


class TestFormatResearchNotes:
    def test_includes_section_headers_and_content(self):
        notes = {
            "facts_and_overview": "fact text",
            "debates_and_uncertain_claims": "debate text",
            "current_relevance": "relevance text",
        }
        text = _format_research_notes(notes)
        assert "FACTS & OVERVIEW" in text
        assert "DEBATES & UNCERTAIN CLAIMS" in text
        assert "CURRENT RELEVANCE" in text
        assert "fact text" in text
        assert "debate text" in text
        assert "relevance text" in text

    def test_preserves_dict_order(self):
        notes = {
            "facts_and_overview": "note-one",
            "debates_and_uncertain_claims": "note-two",
            "current_relevance": "note-three",
        }
        text = _format_research_notes(notes)
        assert text.index("note-one") < text.index("note-two") < text.index("note-three")


class TestStructurePack:
    def test_uses_response_schema_without_grounding_tool(self):
        fake_client = MagicMock()
        pack_json = json.dumps(
            {
                "overview": "o",
                "verified_facts": [],
                "uncertain_claims": [],
                "discussion_axes": ["a"],
                "personal_angles": ["b"],
                "persona_hooks": {"alice": "x", "bob": "y"},
                "conversation_beats": ["c"],
                "user_cheat_sheet": ["d"],
                "sources": [],
            }
        )
        fake_client.models.generate_content.return_value = MagicMock(text=pack_json)

        pack = _structure_pack(fake_client, "AI", "some research notes")

        assert isinstance(pack, TopicPackOutput)
        assert pack.overview == "o"
        _, kwargs = fake_client.models.generate_content.call_args
        config = kwargs["config"]
        assert config.response_mime_type == "application/json"
        assert config.response_schema is TopicPackOutput
        assert config.tools is None

    def test_prompt_includes_research_notes(self):
        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = MagicMock(
            text=json.dumps(
                {
                    "overview": "o",
                    "discussion_axes": ["a"],
                    "personal_angles": ["b"],
                    "persona_hooks": {"alice": "x", "bob": "y"},
                    "conversation_beats": ["c"],
                    "user_cheat_sheet": ["d"],
                }
            )
        )

        _structure_pack(fake_client, "AI", "=== FACTS & OVERVIEW ===\nAI is popular.")

        _, kwargs = fake_client.models.generate_content.call_args
        assert "AI is popular." in kwargs["contents"]
