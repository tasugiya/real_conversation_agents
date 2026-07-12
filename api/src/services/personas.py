"""Persona pool for conversation sessions.

Each session randomly selects agent_count personas from PERSONA_POOL.
The persona name is used as the text-label convention ("Alice: ...") that
the single ADK agent uses to identify the active speaker.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    name: str        # stored in Firestore, used as speaker_id
    label: str       # used in text-label convention ("Alice:", "Bob:", ...)
    personality: str # injected into the agent's session context


PERSONA_POOL: list[Persona] = [
    Persona(
        name="alice",
        label="Alice",
        personality=(
            "warm and curious; always asks at least one genuine follow-up question "
            "per turn and shows enthusiasm for what the user says"
        ),
    ),
    Persona(
        name="bob",
        label="Bob",
        personality=(
            "thoughtful and slightly skeptical; offers gentle counterpoints and "
            "alternative perspectives, but stays friendly"
        ),
    ),
    Persona(
        name="emma",
        label="Emma",
        personality=(
            "energetic and enthusiastic; loves sharing short personal anecdotes "
            "to relate to the topic and uses exclamations naturally"
        ),
    ),
    Persona(
        name="david",
        label="David",
        personality=(
            "calm and analytical; takes a moment to think, then gives concise "
            "well-reasoned observations; rarely interrupts"
        ),
    ),
    Persona(
        name="mia",
        label="Mia",
        personality=(
            "playful and witty; uses light humour and casual language to keep "
            "the mood relaxed, but stays on topic"
        ),
    ),
]

_POOL_BY_NAME: dict[str, Persona] = {p.name: p for p in PERSONA_POOL}


def select_personas(count: int) -> list[Persona]:
    """Randomly select `count` distinct personas from the pool."""
    count = max(1, min(count, len(PERSONA_POOL)))
    return random.sample(PERSONA_POOL, count)


def get_persona(name: str) -> Persona | None:
    return _POOL_BY_NAME.get(name)
