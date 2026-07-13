"""Tests for the stuck-session fix (max_concurrent_sessions self-healing).

Covers:
  - sessions.py: _filter_stale_sessions, _mark_stale_sessions_abandoned,
    and create_session's end-to-end concurrency behavior.
  - ws.py: _finalize_session_update (the finally-block decision logic).
  - end_session still works when called on an "abandoned" session.

All Firestore/agent calls are mocked -- no real network calls.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.routes.sessions import (
    _filter_stale_sessions,
    _mark_stale_sessions_abandoned,
    create_session,
    end_session,
)
from src.routes.ws import _finalize_session_update
from src.schemas.session import CreateSessionRequest


class _FakeDoc:
    def __init__(self, doc_id: str, data: dict):
        self.id = doc_id
        self._data = data

    def to_dict(self) -> dict:
        return self._data


def _session_doc(doc_id: str, started_at: datetime) -> _FakeDoc:
    return _FakeDoc(doc_id, {"status": "created", "started_at": started_at})


class TestFilterStaleSessions:
    def test_fresh_session_stays_active(self):
        now = datetime.now(timezone.utc)
        with patch("src.routes.sessions.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(session_max_duration_seconds=600)
            active, stale = _filter_stale_sessions([_session_doc("a", now)])
        assert len(active) == 1
        assert stale == []

    def test_old_session_is_stale(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(seconds=600 + 120 + 1)  # past max_duration + grace
        with patch("src.routes.sessions.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(session_max_duration_seconds=600)
            active, stale = _filter_stale_sessions([_session_doc("a", old)])
        assert active == []
        assert len(stale) == 1

    def test_session_within_grace_window_stays_active(self):
        now = datetime.now(timezone.utc)
        just_over_duration = now - timedelta(seconds=600 + 60)  # inside 120s grace
        with patch("src.routes.sessions.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(session_max_duration_seconds=600)
            active, stale = _filter_stale_sessions([_session_doc("a", just_over_duration)])
        assert len(active) == 1
        assert stale == []

    def test_missing_started_at_stays_active(self):
        doc = _FakeDoc("a", {"status": "created"})
        with patch("src.routes.sessions.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(session_max_duration_seconds=600)
            active, stale = _filter_stale_sessions([doc])
        assert len(active) == 1
        assert stale == []


class TestMarkStaleSessionsAbandoned:
    def test_updates_each_stale_doc(self):
        now = datetime.now(timezone.utc)
        docs = [_session_doc("a", now), _session_doc("b", now)]
        with patch("src.routes.sessions.firestore_client.update_document") as mock_update:
            _mark_stale_sessions_abandoned(docs)
        assert mock_update.call_count == 2
        ids_updated = {call.args[1] for call in mock_update.call_args_list}
        assert ids_updated == {"a", "b"}
        for call in mock_update.call_args_list:
            assert call.args[2]["status"] == "abandoned"
            assert "ended_at" in call.args[2]

    def test_never_raises_on_firestore_failure(self):
        docs = [_session_doc("a", datetime.now(timezone.utc))]
        with patch(
            "src.routes.sessions.firestore_client.update_document",
            side_effect=Exception("boom"),
        ):
            _mark_stale_sessions_abandoned(docs)  # should not raise


class TestCreateSessionConcurrency:
    def _patched(self, active_docs: list[_FakeDoc], max_concurrent: int = 5, memory_ratio: float | None = None):
        mock_query = MagicMock()
        mock_query.stream.return_value = active_docs
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_client = MagicMock()
        mock_client.collection.return_value = mock_collection

        return (
            patch("src.routes.sessions.firestore_client.get_client", return_value=mock_client),
            patch("src.routes.sessions.firestore_client.create_document"),
            patch("src.routes.sessions.firestore_client.update_document"),
            patch(
                "src.routes.sessions.create_agent_session",
                new_callable=AsyncMock,
                return_value="agent-session-id",
            ),
            patch(
                "src.routes.sessions.get_settings",
                return_value=MagicMock(
                    session_max_duration_seconds=600,
                    max_concurrent_sessions=max_concurrent,
                    memory_pressure_threshold=0.85,
                ),
            ),
            # Default to "unknown" (fail open) so these concurrency-focused
            # tests aren't coupled to whatever cgroup state the test runner
            # happens to have -- BUG-023's own tests cover the real values.
            patch("src.routes.sessions.memory_usage_ratio", return_value=memory_ratio),
        )

    @pytest.mark.asyncio
    async def test_memory_pressure_above_threshold_returns_503(self):
        # BUG-023: proactively reject before an OOM-kill takes the instance
        # down mid-conversation. Concurrency slots are free (0/5) but memory
        # usage is over the 0.85 threshold.
        patches = self._patched([], max_concurrent=5, memory_ratio=0.9)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            body = CreateSessionRequest(topic_pack_id="tp1", agent_count=2)
            with pytest.raises(Exception) as exc_info:
                await create_session(body)
        assert "503" in str(exc_info.value) or getattr(exc_info.value, "status_code", None) == 503

    @pytest.mark.asyncio
    async def test_memory_pressure_below_threshold_does_not_block(self):
        patches = self._patched([], max_concurrent=5, memory_ratio=0.5)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            body = CreateSessionRequest(topic_pack_id="tp1", agent_count=2)
            result = await create_session(body)
        assert result.status == "created"

    @pytest.mark.asyncio
    async def test_all_stale_sessions_do_not_block_creation(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(seconds=600 + 200)
        docs = [_session_doc(str(i), old) for i in range(5)]
        patches = self._patched(docs, max_concurrent=5)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            body = CreateSessionRequest(topic_pack_id="tp1", agent_count=2)
            result = await create_session(body)
        assert result.status == "created"

    @pytest.mark.asyncio
    async def test_fresh_sessions_at_capacity_return_503(self):
        now = datetime.now(timezone.utc)
        docs = [_session_doc(str(i), now) for i in range(2)]
        patches = self._patched(docs, max_concurrent=2)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            body = CreateSessionRequest(topic_pack_id="tp1", agent_count=2)
            with pytest.raises(Exception) as exc_info:
                await create_session(body)
        assert "503" in str(exc_info.value) or getattr(exc_info.value, "status_code", None) == 503

    @pytest.mark.asyncio
    async def test_stale_marking_failure_does_not_block_creation(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(seconds=600 + 200)
        docs = [_session_doc("a", old)]
        mock_query = MagicMock()
        mock_query.stream.return_value = docs
        mock_collection = MagicMock()
        mock_collection.where.return_value = mock_query
        mock_client = MagicMock()
        mock_client.collection.return_value = mock_collection

        with patch("src.routes.sessions.firestore_client.get_client", return_value=mock_client), \
             patch("src.routes.sessions.firestore_client.create_document"), \
             patch(
                 "src.routes.sessions.firestore_client.update_document",
                 side_effect=Exception("firestore down"),
             ), \
             patch(
                 "src.routes.sessions.create_agent_session",
                 new_callable=AsyncMock,
                 return_value="agent-session-id",
             ), \
             patch(
                 "src.routes.sessions.get_settings",
                 return_value=MagicMock(
                     session_max_duration_seconds=600,
                     max_concurrent_sessions=5,
                     memory_pressure_threshold=0.85,
                 ),
             ), \
             patch("src.routes.sessions.memory_usage_ratio", return_value=None):
            body = CreateSessionRequest(topic_pack_id="tp1", agent_count=2)
            result = await create_session(body)
        assert result.status == "created"


class TestFinalizeSessionUpdate:
    def test_graceful_end_from_created_marks_abandoned(self):
        update = _finalize_session_update("created", graceful_end=True, sequence=5)
        assert update["status"] == "abandoned"
        assert "ended_at" in update
        assert update["last_sequence"] == 5

    def test_bare_disconnect_does_not_touch_status(self):
        update = _finalize_session_update("created", graceful_end=False, sequence=5)
        assert "status" not in update
        assert update["last_sequence"] == 5

    def test_does_not_clobber_ending_status(self):
        update = _finalize_session_update("ending", graceful_end=True, sequence=5)
        assert "status" not in update
        assert update["last_sequence"] == 5


class TestEndSessionFromAbandoned:
    @pytest.mark.asyncio
    async def test_completes_review_from_abandoned_status(self):
        session_doc = {"session_id": "s1", "status": "abandoned", "started_at": datetime.now(timezone.utc)}
        fake_review_result = MagicMock(
            summary="ok",
            score_total=10,
            score_communication=5,
            score_language=5,
            conversation_feedback=[],
            grammar_feedback=[],
        )
        with patch("src.routes.sessions.firestore_client.get_document", return_value=session_doc), \
             patch("src.routes.sessions.firestore_client.update_document") as mock_update, \
             patch("src.routes.sessions.firestore_client.create_document"), \
             patch("src.routes.sessions._load_transcript", return_value=[]), \
             patch("src.routes.sessions.generate_review", return_value=fake_review_result):
            result = await end_session("s1")

        assert result.session_id == "s1"
        statuses_set = [
            call.args[2]["status"] for call in mock_update.call_args_list if "status" in call.args[2]
        ]
        assert statuses_set == ["ending", "completed"]
