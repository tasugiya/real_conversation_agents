"""Direct Gemini call for end-of-session Review generation.

Review generation does NOT go through the deployed Agent Engine -- it is a
single structured-output text call, and Agent Engine's session/bidi
machinery adds no value here (see agent_engine_client.py's module docstring
for why Agent Engine is reserved for the live conversation only). This
matches docs/BASIC_DESIGN.md GAI-002 (Gemini API / Vertex AI Gemini for
grammar feedback and summaries, as distinct from the Live API path).
"""

from __future__ import annotations

import json

import vertexai
from pydantic import BaseModel
from vertexai.generative_models import GenerationConfig, GenerativeModel

from ..config import get_settings

MODEL_NAME = "gemini-2.5-flash"

REVIEW_INSTRUCTION = """
You will be given a transcript of a short English conversation practice
session between a user and AI characters.

Produce a review with exactly these fields:
- summary: 1-2 sentences in Japanese summarising the user's overall performance.
- score_communication: integer 0-50 measuring participation quality (did the user
  ask questions, respond naturally, keep the conversation going?).
- score_language: integer 0-50 measuring grammar and vocabulary accuracy.
- score_total: score_communication + score_language (must equal the sum).
- conversation_feedback: list of 2-3 SHORT tips in Japanese on how the user can
  improve conversation flow (e.g. asking follow-ups, avoiding long silences).
- grammar_feedback: up to 3 items, each with:
    original: the exact phrase the user said (from the transcript only)
    suggestion: a corrected or improved version
    explanation_ja: brief Japanese explanation of why

Rules:
- Only reference lines labelled as the user (role="user") in the transcript.
- Do not invent utterances.
- If the transcript is empty or too short, return summary="会話記録が不足しています。",
  score_communication=0, score_language=0, score_total=0, empty lists.
"""


class GrammarFeedbackItem(BaseModel):
    original: str
    suggestion: str
    explanation_ja: str


class ReviewResult(BaseModel):
    summary: str
    score_communication: int = 0
    score_language: int = 0
    score_total: int = 0
    conversation_feedback: list[str] = []
    grammar_feedback: list[GrammarFeedbackItem] = []


_initialized = False


def _ensure_init() -> None:
    global _initialized
    if _initialized:
        return
    settings = get_settings()
    vertexai.init(project=settings.gcp_project_id, location=settings.gcp_region)
    _initialized = True


def generate_review(transcript: list[dict]) -> ReviewResult:
    """Never raises: falls back to a safe minimal review on any failure, per
    NFR-101/AC-009 (external API failure must not break the app).
    """
    try:
        _ensure_init()
        model = GenerativeModel(MODEL_NAME, system_instruction=REVIEW_INSTRUCTION)
        response = model.generate_content(
            json.dumps(transcript, ensure_ascii=False),
            generation_config=GenerationConfig(
                response_mime_type="application/json",
                response_schema=ReviewResult.model_json_schema(),
            ),
        )
        return ReviewResult.model_validate_json(response.text)
    except Exception:
        return ReviewResult(
            summary="Review generation is temporarily unavailable.",
            score_total=0,
            score_communication=0,
            score_language=0,
        )
