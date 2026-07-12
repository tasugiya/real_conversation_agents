"""Topic Pack generation using Gemini 2.5 Flash + Google Search Grounding.

Called synchronously from the Cloud Tasks internal endpoint
(routes/topic_packs.py → POST /internal/topic-packs/{id}/generate).

Flow:
  1. Build a research prompt from topic_title (or topic_id as fallback).
  2. Call Gemini with GoogleSearchRetrieval so it can look up current info.
  3. Parse the structured output into Topic Pack fields.
  4. Save to Firestore.

Falls back to a minimal hard-coded pack on any error so the conversation
can still start.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel, Field

from ..config import get_settings
from ..services import firestore_client

logger = logging.getLogger("topic_pack_generate")

TOPIC_PACKS_COLLECTION = "topic_packs"
MODEL_NAME = "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# Structured output schema
# ---------------------------------------------------------------------------

class PersonaHooks(BaseModel):
    alice: str = Field(description="Alice's interest or angle on this topic")
    bob: str = Field(description="Bob's interest or angle on this topic")


class TopicPackOutput(BaseModel):
    overview: str = Field(description="1-2 sentence summary of the topic for conversation context")
    verified_facts: list[str] = Field(
        default_factory=list,
        description="Up to 5 well-established facts about this topic that a persona can state confidently",
    )
    uncertain_claims: list[str] = Field(
        default_factory=list,
        description="Statements that are debated or unverified; personas should frame these as opinions",
    )
    discussion_axes: list[str] = Field(
        description="3-5 angles or questions that can spark interesting conversation",
    )
    personal_angles: list[str] = Field(
        description="2-3 ways to connect the topic to the user's personal experience",
    )
    persona_hooks: PersonaHooks = Field(
        description="How each persona (Alice / Bob) relates to this topic",
    )
    conversation_beats: list[str] = Field(
        description="3-5 ordered milestones for the conversation if the user doesn't guide it",
    )
    user_cheat_sheet: list[str] = Field(
        description="5-8 short English phrases the user can actually say to join the conversation",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Up to 3 URLs or source descriptions grounding the facts above",
    )


_RESEARCH_PROMPT_TEMPLATE = """
You are preparing a Topic Pack for a short English conversation practice
session. The topic is: "{topic}"

Using your search tool, gather current, accurate information about this topic.
Then produce a Topic Pack as structured JSON with exactly these fields:

- overview: 1-2 sentences summarising the topic for conversation context
- verified_facts: up to 5 well-established facts a persona can state confidently
- uncertain_claims: up to 3 debated/unverified statements (frame as opinions)
- discussion_axes: 3-5 angles or questions to spark interesting conversation
- personal_angles: 2-3 ways to connect the topic to the user's daily life
- persona_hooks:
    alice: how Alice (warm, curious, asks follow-ups) would approach this topic
    bob: how Bob (slightly skeptical, offers counterpoints) would approach this topic
- conversation_beats: 3-5 ordered milestones if the user doesn't guide the conversation
- user_cheat_sheet: 5-8 short English phrases the user can say to join in
- sources: up to 3 URLs or source descriptions you found

Keep all content appropriate for English language learners (B1-B2 level).
Focus on facts, interesting angles, and phrases relevant as of today ({today}).
"""


def generate(topic_pack_id: str, topic_id: str, topic_title: str | None = None) -> None:
    """Generate a Topic Pack and save it to Firestore.

    topic_title takes priority over topic_id as the research query.
    Falls back to a minimal fixed pack on any error.
    """
    topic = topic_title or topic_id.replace("_", " ").replace("-", " ")

    try:
        pack = _generate_with_gemini(topic)
    except Exception as exc:
        logger.exception("topic_pack_generate: Gemini research failed for %r: %s", topic, exc)
        pack = _fallback_pack(topic)

    firestore_client.update_document(
        TOPIC_PACKS_COLLECTION,
        topic_pack_id,
        {
            "status": "ready",
            "overview": pack.overview,
            "verified_facts": pack.verified_facts,
            "uncertain_claims": pack.uncertain_claims,
            "discussion_axes": pack.discussion_axes,
            "personal_angles": pack.personal_angles,
            "persona_hooks": {
                "alice": pack.persona_hooks.alice,
                "bob": pack.persona_hooks.bob,
            },
            "conversation_beats": pack.conversation_beats,
            "user_cheat_sheet": pack.user_cheat_sheet,
            "sources": pack.sources,
            "is_dummy": False,
            "generated_at": datetime.now(timezone.utc),
        },
    )


def _generate_with_gemini(topic: str) -> TopicPackOutput:
    settings = get_settings()
    client = genai.Client(
        vertexai=True,
        project=settings.gcp_project_id,
        location=settings.gcp_region,
    )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prompt = _RESEARCH_PROMPT_TEMPLATE.format(topic=topic, today=today)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
            temperature=0.3,
            response_mime_type="application/json",
            response_schema=TopicPackOutput,
        ),
    )

    return TopicPackOutput.model_validate_json(response.text)


def _fallback_pack(topic: str) -> TopicPackOutput:
    """Minimal pack used when Gemini research fails."""
    return TopicPackOutput(
        overview=f"A casual conversation about {topic}.",
        verified_facts=[],
        uncertain_claims=[],
        discussion_axes=[
            f"What do you know about {topic}?",
            "What's your opinion on this?",
            "How does this affect your daily life?",
        ],
        personal_angles=[
            f"Ask the user about their own experience with {topic}.",
        ],
        persona_hooks=PersonaHooks(
            alice="genuinely curious, asks follow-up questions",
            bob="slightly more skeptical, offers a different angle",
        ),
        conversation_beats=[
            "Introduce the topic casually",
            "Ask the user a question",
            "React and ask a follow-up",
        ],
        user_cheat_sheet=[
            "I think...",
            "That reminds me of...",
            "What about you?",
            "I'm not sure, but...",
            "Could you tell me more?",
        ],
        sources=[],
    )
