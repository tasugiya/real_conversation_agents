"""Tests for agent_engine_client's Vertex AI / session-service wiring.

Covers two regression guards:
  - "No API key was provided" incident: ADK builds its own google-genai
    Client internally and does not read vertexai.init()'s global state, so
    the Gemini model passed to Agent() must carry explicit client_kwargs
    (vertexai=True, project, location).
  - The 2026-07-12 OOM incident: InMemorySessionService never expired
    sessions and isn't shared across Cloud Run instances. _get_runner() must
    construct VertexAiSessionService with the bare numeric reasoning-engine
    id (not the full resource name), and create_agent_session() must pass a
    TTL so Vertex AI expires sessions server-side even if nothing ever calls
    delete_session().
See LOG.md for both incident writeups. Agent/Gemini/Runner/
VertexAiSessionService are all mocked -- no real ADK/GCP calls needed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.services.agent_engine_client as agent_engine_client


def _patched(**settings_overrides):
    settings = MagicMock(
        gcp_project_id="proj-1",
        gcp_region="us-central1",
        agent_engine_resource_name="projects/proj-1/locations/us-central1/reasoningEngines/8246617034029268992",
    )
    for key, value in settings_overrides.items():
        setattr(settings, key, value)
    return (
        patch("src.services.agent_engine_client.get_settings", return_value=settings),
        patch("src.services.agent_engine_client.VertexAiSessionService"),
        patch("src.services.agent_engine_client.Gemini"),
        patch("src.services.agent_engine_client.Agent"),
        patch("src.services.agent_engine_client.Runner"),
    )


class TestGetRunnerVertexAIWiring:
    def setup_method(self):
        # _get_runner caches its result in a module-level singleton; reset it
        # so each test observes a fresh construction.
        agent_engine_client._runner = None

    def teardown_method(self):
        agent_engine_client._runner = None

    def test_gemini_model_receives_vertexai_client_kwargs(self):
        settings_p, session_p, gemini_p, agent_p, runner_p = _patched()
        with settings_p, session_p, gemini_p as mock_gemini, agent_p, runner_p as mock_runner_cls:
            mock_gemini.return_value = MagicMock()
            mock_runner_cls.return_value = MagicMock()

            agent_engine_client._get_runner()

        _, kwargs = mock_gemini.call_args
        assert kwargs["client_kwargs"] == {
            "vertexai": True,
            "project": "proj-1",
            "location": "us-central1",
        }
        assert kwargs["model"] == agent_engine_client.MODEL_NAME

    def test_agent_receives_gemini_instance_not_bare_string(self):
        settings_p, session_p, gemini_p, agent_p, runner_p = _patched()
        with settings_p, session_p, gemini_p as mock_gemini, agent_p as mock_agent, runner_p as mock_runner_cls:
            fake_model = MagicMock()
            mock_gemini.return_value = fake_model
            mock_runner_cls.return_value = MagicMock()

            agent_engine_client._get_runner()

        _, agent_kwargs = mock_agent.call_args
        assert agent_kwargs["model"] is fake_model

    def test_runner_is_cached_across_calls(self):
        settings_p, session_p, gemini_p, agent_p, runner_p = _patched()
        with settings_p, session_p, gemini_p, agent_p, runner_p as mock_runner_cls:
            mock_runner_cls.return_value = MagicMock()

            first = agent_engine_client._get_runner()
            second = agent_engine_client._get_runner()

        assert first is second
        assert mock_runner_cls.call_count == 1


class TestGetRunnerSessionServiceWiring:
    def setup_method(self):
        agent_engine_client._runner = None

    def teardown_method(self):
        agent_engine_client._runner = None

    def test_vertex_ai_session_service_receives_bare_reasoning_engine_id(self):
        settings_p, session_p, gemini_p, agent_p, runner_p = _patched()
        with settings_p, session_p as mock_session_cls, gemini_p, agent_p, runner_p as mock_runner_cls:
            mock_session_cls.return_value = MagicMock()
            mock_runner_cls.return_value = MagicMock()

            agent_engine_client._get_runner()

        _, kwargs = mock_session_cls.call_args
        assert kwargs["project"] == "proj-1"
        assert kwargs["location"] == "us-central1"
        assert kwargs["agent_engine_id"] == "8246617034029268992"

    def test_runner_receives_the_constructed_session_service(self):
        settings_p, session_p, gemini_p, agent_p, runner_p = _patched()
        with settings_p, session_p as mock_session_cls, gemini_p, agent_p, runner_p as mock_runner_cls:
            fake_session_service = MagicMock()
            mock_session_cls.return_value = fake_session_service
            mock_runner_cls.return_value = MagicMock()

            agent_engine_client._get_runner()

        _, runner_kwargs = mock_runner_cls.call_args
        assert runner_kwargs["session_service"] is fake_session_service


class TestExtractReasoningEngineId:
    def test_extracts_trailing_numeric_id_from_full_resource_name(self):
        result = agent_engine_client._extract_reasoning_engine_id(
            "projects/11418767319/locations/us-central1/reasoningEngines/8246617034029268992"
        )
        assert result == "8246617034029268992"

    def test_bare_id_passes_through_unchanged(self):
        assert agent_engine_client._extract_reasoning_engine_id("8246617034029268992") == "8246617034029268992"


class TestCreateAgentSessionTTL:
    @pytest.mark.asyncio
    async def test_create_session_called_with_ttl(self):
        fake_session = MagicMock(id="session-abc")
        fake_session_service = MagicMock()
        fake_session_service.create_session = AsyncMock(return_value=fake_session)
        fake_runner = MagicMock(session_service=fake_session_service)

        with patch("src.services.agent_engine_client._get_runner", return_value=fake_runner):
            result = await agent_engine_client.create_agent_session(user_id="user-1")

        assert result == "session-abc"
        fake_session_service.create_session.assert_awaited_once_with(
            app_name=agent_engine_client._APP_NAME,
            user_id="user-1",
            ttl=agent_engine_client._SESSION_TTL,
        )
