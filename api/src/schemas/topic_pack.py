"""Topic / Topic Pack request/response models."""

from datetime import datetime

from pydantic import BaseModel


class Topic(BaseModel):
    topic_id: str
    title: str


class TopicsResponse(BaseModel):
    topics: list[Topic]


class CreateTopicPackRequest(BaseModel):
    topic_id: str
    topic_title: str | None = None  # Human-readable title; used as research query


class CreateTopicPackAcceptedResponse(BaseModel):
    job_id: str
    topic_pack_id: str
    status: str = "pending"


class TopicPack(BaseModel):
    topic_pack_id: str
    topic_id: str
    status: str  # "pending" | "ready" | "failed"
    overview: str | None = None
    verified_facts: list[str] = []
    uncertain_claims: list[str] = []
    discussion_axes: list[str] = []
    personal_angles: list[str] = []
    persona_hooks: dict[str, str] = {}
    conversation_beats: list[str] = []
    user_cheat_sheet: list[str] = []
    sources: list[str] = []
    is_dummy: bool = True
    generated_at: datetime | None = None
    expires_at: datetime | None = None
