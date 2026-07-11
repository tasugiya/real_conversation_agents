"""Review agent: generates an end-of-session review synchronously.

Unlike the root conversation agent, this does not run in bidi/live mode. It
is invoked once, after the session ends, with the conversation transcript,
via a regular (non-streaming) call -- consistent with docs/infra/01_ARCHITECTURE.md
§5 (Review generation stays synchronous, not queued).
"""

from google.adk.agents import Agent
from pydantic import BaseModel, Field

# Non-live model. Re-verify the exact name against
# https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini
# before relying on this in an environment.
MODEL_NAME = "gemini-2.5-flash"


class GrammarFeedbackItem(BaseModel):
    original: str
    suggestion: str
    explanation_ja: str


class ReviewOutput(BaseModel):
    summary: str = Field(description="1-2 sentence summary of the conversation")
    score_total: int = Field(ge=0, le=100)
    grammar_feedback: list[GrammarFeedbackItem] = Field(default_factory=list)


REVIEW_INSTRUCTION = """
You will be given a transcript of a short English conversation practice
session between a user and AI characters. Produce a short review for the
user: a one to two sentence summary, an overall score from 0-100, and up to
3 grammar or phrasing improvement suggestions drawn only from the user's own
lines. Do not invent lines the user didn't say. If the transcript is too
short or unclear, still return a valid response with a low score and an
empty grammar_feedback list rather than failing.
"""

review_agent = Agent(
    name="review_agent",
    model=MODEL_NAME,
    instruction=REVIEW_INSTRUCTION,
    output_schema=ReviewOutput,
)
