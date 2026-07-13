"""Topic Pack generation reference implementation.

In the PoC architecture, Topic Pack generation runs inside the API (Cloud Run)
via Cloud Tasks → api/src/tasks/topic_pack_generate.py, NOT inside Agent Engine.
This module mirrors that logic for documentation and future Agent Engine use.

If the architecture moves Topic Pack generation into Agent Engine, this file
becomes the entry point. For now it delegates to the same Gemini + Search
Grounding approach used by the API.

See: api/src/tasks/topic_pack_generate.py (canonical implementation)
     docs/backend/03_AGENT_ORCHESTRATION_DRAFT.md §4 (workflow design)
"""

# This file is intentionally thin -- the real implementation is in the API
# task runner. Import and re-export the core output schema so tests can
# reference it without duplicating the definition.
from pydantic import BaseModel, Field


class PersonaHooks(BaseModel):
    alice: str = Field(description="Alice's angle on the topic")
    bob: str = Field(description="Bob's angle on the topic")


class TopicPackOutput(BaseModel):
    overview: str
    verified_facts: list[str] = []
    uncertain_claims: list[str] = []
    discussion_axes: list[str]
    personal_angles: list[str]
    persona_hooks: PersonaHooks
    conversation_beats: list[str]
    user_cheat_sheet: list[str]
    sources: list[str] = []
