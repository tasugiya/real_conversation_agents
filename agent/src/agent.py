"""Root agent for the real-time multi-persona conversation (connectivity-first pass).

sub_agents / transfer_to_agent is intentionally NOT used here. ADK's live/bidi
streaming mode has open reliability issues delegating to sub-agents
(google/adk-python #2382, #3878, #2994; google/adk-docs #469): the root agent
responds but delegation to a sub-agent frequently doesn't happen. Until that
stabilizes, a single agent plays multiple personas through instruction text
and a spoken naming convention (see prompts/root_instruction.py). This keeps
the very first end-to-end connectivity pass (frontend <-> Cloud Run API <->
Agent Engine) on the most reliable path available.

Persona voice differentiation (one distinct voice per persona) and true
Director -> Persona delegation are deferred; see docs/backend/03_AGENT_ORCHESTRATION_DRAFT.md
§14 for the fallback tiering this follows.
"""

from google.adk.agents import Agent

from .prompts.root_instruction import ROOT_INSTRUCTION

# Vertex AI Gemini Live model identifier. Re-verify against
# https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api before
# relying on this in an environment, since Live model names change.
MODEL_NAME = "gemini-live-2.5-flash-native-audio"

root_agent = Agent(
    name="conversation_agent",
    model=MODEL_NAME,
    instruction=ROOT_INSTRUCTION,
)
