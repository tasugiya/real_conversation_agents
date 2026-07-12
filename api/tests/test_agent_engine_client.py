"""Tests for agent_engine_client._get_runner's Vertex AI wiring.

Regression guard for the "No API key was provided" incident: ADK builds its
own google-genai Client internally and does not read vertexai.init()'s
global state, so the Gemini model passed to Agent() must carry explicit
client_kwargs (vertexai=True, project, location). See LOG.md for the
incident writeup. Agent/Gemini/Runner are all mocked -- no real ADK/GCP
calls needed.
"""

from unittest.mock import MagicMock, patch

import src.services.agent_engine_client as agent_engine_client


class TestGetRunnerVertexAIWiring:
    def setup_method(self):
        # _get_runner caches its result in a module-level singleton; reset it
        # so each test observes a fresh construction.
        agent_engine_client._runner = None

    def teardown_method(self):
        agent_engine_client._runner = None

    def test_gemini_model_receives_vertexai_client_kwargs(self):
        with patch("src.services.agent_engine_client.get_settings") as mock_settings, \
             patch("src.services.agent_engine_client.Gemini") as mock_gemini, \
             patch("src.services.agent_engine_client.Agent") as mock_agent, \
             patch("src.services.agent_engine_client.Runner") as mock_runner_cls:
            mock_settings.return_value = MagicMock(gcp_project_id="proj-1", gcp_region="us-central1")
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
        with patch("src.services.agent_engine_client.get_settings") as mock_settings, \
             patch("src.services.agent_engine_client.Gemini") as mock_gemini, \
             patch("src.services.agent_engine_client.Agent") as mock_agent, \
             patch("src.services.agent_engine_client.Runner") as mock_runner_cls:
            mock_settings.return_value = MagicMock(gcp_project_id="proj-1", gcp_region="us-central1")
            fake_model = MagicMock()
            mock_gemini.return_value = fake_model
            mock_runner_cls.return_value = MagicMock()

            agent_engine_client._get_runner()

        _, agent_kwargs = mock_agent.call_args
        assert agent_kwargs["model"] is fake_model

    def test_runner_is_cached_across_calls(self):
        with patch("src.services.agent_engine_client.get_settings") as mock_settings, \
             patch("src.services.agent_engine_client.Gemini"), \
             patch("src.services.agent_engine_client.Agent"), \
             patch("src.services.agent_engine_client.Runner") as mock_runner_cls:
            mock_settings.return_value = MagicMock(gcp_project_id="proj-1", gcp_region="us-central1")
            mock_runner_cls.return_value = MagicMock()

            first = agent_engine_client._get_runner()
            second = agent_engine_client._get_runner()

        assert first is second
        assert mock_runner_cls.call_count == 1
