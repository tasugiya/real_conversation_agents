"""Basic local sanity check for the agent definition and AdkApp wiring.

This does NOT exercise real bidi streaming (that needs network access to the
Gemini Live API and is verified manually / in the dev environment per
docs/DEVOPS.md's test strategy). It only confirms the agent/app can be
constructed and a session created, to catch import and config errors early
and cheaply in CI (agent-ci job in .github/workflows/ci.yml).
"""

from vertexai.preview import reasoning_engines

from src.agent import root_agent


def test_agent_app_builds_and_creates_session():
    app = reasoning_engines.AdkApp(agent=root_agent)
    session = app.create_session(user_id="test_user")
    assert session is not None


def test_review_agent_imports():
    from src.review.review_agent import review_agent

    assert review_agent.name == "review_agent"


def test_dummy_topic_pack_has_expected_shape():
    from src.topic_pack_workflow.dummy import generate_dummy_topic_pack, list_topics

    topics = list_topics()
    assert len(topics) >= 1

    pack = generate_dummy_topic_pack(topics[0]["topic_id"])
    assert pack["topic_id"] == topics[0]["topic_id"]
    assert pack["is_dummy"] is True
