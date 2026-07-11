"""Dummy Topic Pack generation (案A: duplicated here, does not call Agent
Engine at all). X API / Search Grounding research is not implemented yet
(docs/backend/03_AGENT_ORCHESTRATION_DRAFT.md §4).

Runs synchronously inside the Cloud Tasks-dispatched request handler.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..services import firestore_client

TOPIC_PACKS_COLLECTION = "topic_packs"

_DUMMY_OVERVIEWS = {
    "campus_life": "A casual conversation about campus life.",
    "weekend_plans": "A casual conversation about weekend plans.",
    "favorite_media": "A casual conversation about favorite movies or shows.",
}


def generate(topic_pack_id: str, topic_id: str) -> None:
    overview = _DUMMY_OVERVIEWS.get(topic_id, f"A casual conversation about {topic_id}.")

    firestore_client.update_document(
        TOPIC_PACKS_COLLECTION,
        topic_pack_id,
        {
            "status": "ready",
            "overview": overview,
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
            "user_cheat_sheet": [
                "I think...",
                "That reminds me of...",
                "What about you?",
            ],
            "sources": [],
            "is_dummy": True,
            "generated_at": datetime.now(timezone.utc),
        },
    )
