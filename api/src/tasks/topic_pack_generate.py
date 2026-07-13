"""Topic Pack generation via a two-stage Gemini pipeline.

Called synchronously from the Cloud Tasks internal endpoint
(routes/topic_packs.py → POST /internal/topic-packs/{id}/generate).

Flow:
  1. Stage 1 (parallel, grounded, unstructured): run several Gemini calls in
     parallel, each using the google_search grounding tool to research one
     facet of the topic (facts, debates, current relevance). Each call
     returns plain bullet-point text, not JSON.
  2. Stage 2 (single, non-grounded, structured): feed the concatenated
     research notes from stage 1 into one more Gemini call with
     response_mime_type="application/json" + response_schema=TopicPackOutput
     to get the final structured Topic Pack.
  3. Save to Firestore.

Falls back to a minimal hard-coded pack on any error so the conversation can
always start.

Why two stages instead of one call:
  google_search grounding and response_mime_type/response_schema are mutually
  exclusive in the Gemini API -- combining them in a single call either
  returns 400 or makes the model ignore the schema and return free text
  (JSON decode failures). Splitting grounded research (stage 1) from
  structured synthesis (stage 2) avoids that incompatibility while still
  letting the model search the live web, which a previous iteration using
  the Google Custom Search API (CSE) could not do (CSE is scoped to a
  Programmable Search Engine's configured sites, not the general web).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
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


# ---------------------------------------------------------------------------
# Stage 1 prompts: parallel grounded research facets
# ---------------------------------------------------------------------------

_BULLET_FORMAT_INSTRUCTIONS = """
Use the google_search tool to verify what you can. Write ONLY plain bullet
lines in exactly this format, nothing else (no preamble, no headers, no
markdown):
- <content> (source: <url or "general knowledge">)

Keep language appropriate for English learners (B1-B2 level).
"""

_FACTS_PROMPT_TEMPLATE = """
Research the topic "{topic}" for a short English conversation practice
session. List 5-8 well-established, verifiable facts about it, plus a
1-2 sentence overview of the topic overall.
""" + _BULLET_FORMAT_INSTRUCTIONS

_DEBATES_PROMPT_TEMPLATE = """
Research the topic "{topic}" for a short English conversation practice
session. List 3-6 points that are controversial, debated, or unverified --
write each as a claim or opinion people hold, NOT as an established fact.
""" + _BULLET_FORMAT_INSTRUCTIONS

_RELEVANCE_PROMPT_TEMPLATE = """
Research the topic "{topic}" for a short English conversation practice
session. Today's date is {today}. List 4-6 points covering: why this topic
is relevant or interesting right now (recent developments, trends), and
everyday/personal-life angles an ordinary person could relate to.
""" + _BULLET_FORMAT_INSTRUCTIONS

_RESEARCH_FACETS: dict[str, str] = {
    "facts_and_overview": _FACTS_PROMPT_TEMPLATE,
    "debates_and_uncertain_claims": _DEBATES_PROMPT_TEMPLATE,
    "current_relevance": _RELEVANCE_PROMPT_TEMPLATE,
}

_RESEARCH_SECTION_LABELS: dict[str, str] = {
    "facts_and_overview": "FACTS & OVERVIEW",
    "debates_and_uncertain_claims": "DEBATES & UNCERTAIN CLAIMS",
    "current_relevance": "CURRENT RELEVANCE",
}


# ---------------------------------------------------------------------------
# Stage 2 prompt: non-grounded structured synthesis
# ---------------------------------------------------------------------------

_STRUCTURE_PROMPT_TEMPLATE = """
You are preparing a Topic Pack for a short English conversation practice
session. The topic is: "{topic}"

Below are research notes gathered from web-grounded search, organized into
labeled sections:

{research_notes}

Using these notes (and general knowledge to fill gaps), produce a Topic Pack
with:

- overview: 1-2 sentences summarising the topic for conversation context
- verified_facts: up to 5 well-established facts a persona can state
  confidently (draw mainly from FACTS & OVERVIEW)
- uncertain_claims: up to 3 debated/unverified statements, framed as opinions
  (draw mainly from DEBATES & UNCERTAIN CLAIMS)
- discussion_axes: 3-5 angles or questions to spark interesting conversation
  (draw mainly from CURRENT RELEVANCE, plus general knowledge)
- personal_angles: 2-3 ways to connect the topic to the user's daily life
- persona_hooks:
    alice: how Alice (warm, curious, asks follow-ups) would approach this topic
    bob: how Bob (slightly skeptical, offers counterpoints) would approach this topic
- conversation_beats: 3-5 ordered milestones if the user doesn't guide the conversation
- user_cheat_sheet: 5-8 short English phrases the user can say to join in
- sources: up to 3 distinct source URLs mentioned in the notes above (skip
  any tagged "general knowledge")

persona_hooks, conversation_beats, and user_cheat_sheet are conversation
design, not research -- synthesize them creatively, they don't need to map
1:1 to a specific note above.

Keep all content appropriate for English language learners (B1-B2 level).
Date today: {today}.
"""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(topic_pack_id: str, topic_id: str, topic_title: str | None = None) -> None:
    """Generate a Topic Pack and save it to Firestore.

    topic_title takes priority over topic_id as the research query.
    Falls back to a minimal fixed pack on any error.
    """
    topic = topic_title or topic_id.replace("_", " ").replace("-", " ")

    try:
        pack = _generate_with_gemini(topic)
    except Exception as exc:
        logger.exception("topic_pack_generate: generation failed for %r: %s", topic, exc)
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


# ---------------------------------------------------------------------------
# Stage 1: parallel grounded research
# ---------------------------------------------------------------------------

def _research_facet(client: genai.Client, topic: str, facet_prompt_template: str, today: str) -> str:
    """Run one grounded research call. Raises on failure -- caller catches."""
    prompt = facet_prompt_template.format(topic=topic, today=today)
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            temperature=0.3,
            tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
        ),
    )
    return response.text


def _run_research(client: genai.Client, topic: str) -> dict[str, str]:
    """Run all research facets in parallel. A single facet's failure doesn't
    abort the others -- it's replaced with a placeholder so stage 2 can still
    proceed on whatever research succeeded plus general knowledge.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    notes: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=len(_RESEARCH_FACETS)) as pool:
        future_to_name = {
            pool.submit(_research_facet, client, topic, prompt_template, today): name
            for name, prompt_template in _RESEARCH_FACETS.items()
        }
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            try:
                notes[name] = future.result()
            except Exception as exc:
                logger.warning("topic_pack_generate: research facet %r failed: %s", name, exc)
                notes[name] = "(no research results for this facet)"

    return {name: notes[name] for name in _RESEARCH_FACETS}


def _format_research_notes(notes: dict[str, str]) -> str:
    """Render facet research notes as labeled sections for the stage-2 prompt."""
    return "\n\n".join(
        f"=== {_RESEARCH_SECTION_LABELS[name]} ===\n{notes[name]}" for name in notes
    )


# ---------------------------------------------------------------------------
# Stage 2: non-grounded structured synthesis
# ---------------------------------------------------------------------------

def _structure_pack(client: genai.Client, topic: str, research_notes: str) -> TopicPackOutput:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prompt = _STRUCTURE_PROMPT_TEMPLATE.format(topic=topic, research_notes=research_notes, today=today)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            temperature=0.3,
            response_mime_type="application/json",
            response_schema=TopicPackOutput,
        ),
    )

    return TopicPackOutput.model_validate_json(response.text)


def _generate_with_gemini(topic: str) -> TopicPackOutput:
    settings = get_settings()
    client = genai.Client(
        vertexai=True,
        project=settings.gcp_project_id,
        location=settings.gcp_region,
    )

    research_notes = _format_research_notes(_run_research(client, topic))
    return _structure_pack(client, topic, research_notes)


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

def _fallback_pack(topic: str) -> TopicPackOutput:
    """Minimal pack used when Gemini generation fails."""
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
