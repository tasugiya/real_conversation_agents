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
session between a user and AI characters. Produce a short review for the
user: a one to two sentence summary, an overall score from 0-100, and up to
3 grammar or phrasing improvement suggestions drawn only from the user's own
lines. Do not invent lines the user didn't say. If the transcript is too
short or unclear, still return a valid response with a low score and an
empty grammar_feedback list rather than failing.
"""


class GrammarFeedbackItem(BaseModel):
    original: str
    suggestion: str
    explanation_ja: str


class ReviewResult(BaseModel):
    summary: str
    score_total: int
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
        return ReviewResult(summary="Review generation is temporarily unavailable.", score_total=0)
