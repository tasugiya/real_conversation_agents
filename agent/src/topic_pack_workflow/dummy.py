"""Dummy Topic Pack generator.

X API / Google Search Grounding research (docs/backend/03_AGENT_ORCHESTRATION_DRAFT.md
§4) is not implemented yet. This returns a small fixed set of topics and a
fixed-shape Topic Pack so the rest of the pipeline (Cloud Tasks -> Firestore
-> frontend) can be wired and tested end-to-end. Swap this module's internals
for the real workflow later without changing its call signature.
"""

import uuid
from datetime import datetime, timezone

FIXED_TOPICS = [
    {"topic_id": "campus_life", "title": "Campus life"},
    {"topic_id": "weekend_plans", "title": "Weekend plans"},
    {"topic_id": "favorite_media", "title": "Favorite movies or shows"},
]


def list_topics() -> list[dict]:
    return FIXED_TOPICS


def generate_dummy_topic_pack(topic_id: str) -> dict:
    topic = next(
        (t for t in FIXED_TOPICS if t["topic_id"] == topic_id), FIXED_TOPICS[0]
    )
    return {
        "topic_pack_id": str(uuid.uuid4()),
        "topic_id": topic["topic_id"],
        "overview": f"A casual conversation about {topic['title'].lower()}.",
        "verified_facts": [],
        "uncertain_claims": [],
        "discussion_axes": [
            "What do you usually do?",
            "What's something you'd recommend?",
        ],
        "personal_angles": [
            "Ask the user about their own experience with this topic."
        ],
        "persona_hooks": {
            "alice": "genuinely curious, asks follow-ups",
            "bob": "slightly more skeptical, offers a different angle",
        },
        "conversation_beats": [
            "Introduce the topic casually",
            "Ask the user a question",
            "React and ask a follow-up",
        ],
        "user_cheat_sheet": ["I think...", "That reminds me of...", "What about you?"],
        "sources": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "is_dummy": True,
    }
