"""Review agent: generates an end-of-session review synchronously.

Unlike the root conversation agent, this does not run in bidi/live mode. It
is invoked once, after the session ends, with the conversation transcript,
via a regular (non-streaming) call -- consistent with docs/infra/01_ARCHITECTURE.md
§5 (Review generation stays synchronous, not queued).

Keep ReviewOutput in sync with:
  api/src/services/gemini_client.py ReviewResult
  api/src/schemas/session.py ReviewResponse
"""

from google.adk.agents import Agent
from pydantic import BaseModel, Field

# Non-live model. Re-verify the exact name against
# https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini
# before relying on this in an environment.
MODEL_NAME = "gemini-2.5-flash"


class GrammarFeedbackItem(BaseModel):
    original: str = Field(description="Exact phrase the user said (from transcript only)")
    suggestion: str = Field(description="Corrected or improved version")
    explanation_ja: str = Field(description="Brief Japanese explanation")


class ReviewOutput(BaseModel):
    summary: str = Field(description="1-2 sentence summary in Japanese")
    score_communication: int = Field(
        ge=0, le=50,
        description="0-50: participation quality, question-asking, naturalness",
    )
    score_language: int = Field(
        ge=0, le=50,
        description="0-50: grammar and vocabulary accuracy",
    )
    score_total: int = Field(
        ge=0, le=100,
        description="score_communication + score_language",
    )
    conversation_feedback: list[str] = Field(
        default_factory=list,
        description="2-3 short tips in Japanese on conversation flow improvement",
    )
    grammar_feedback: list[GrammarFeedbackItem] = Field(
        default_factory=list,
        description="Up to 3 grammar/phrasing corrections drawn from user lines only",
    )


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

review_agent = Agent(
    name="review_agent",
    model=MODEL_NAME,
    instruction=REVIEW_INSTRUCTION,
    output_schema=ReviewOutput,
)
