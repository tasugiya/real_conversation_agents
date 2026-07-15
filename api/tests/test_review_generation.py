"""Tests for review generation robustness (BUG-032).

Firestore documents carry a created_at DatetimeWithNanoseconds that
json.dumps cannot serialise. Every review for a session with at least one
saved message silently fell into generate_review's fallback branch
("Review generation is temporarily unavailable."). Two layers of defence:
  - _load_transcript projects messages to JSON-safe fields only
  - generate_review serialises with default=str and logs failures
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.routes.sessions import _load_transcript
from src.services.gemini_client import ReviewResult, generate_review


def _fake_doc(data: dict) -> MagicMock:
    doc = MagicMock()
    doc.to_dict.return_value = data
    return doc


class TestLoadTranscriptProjection:
    def test_strips_non_json_safe_fields(self):
        raw = {
            "session_id": "s1",
            "speaker_id": "alice",
            "role": "assistant",
            "transcript": "Hello!",
            "status": "final",
            "created_at": datetime(2026, 7, 15, tzinfo=timezone.utc),
        }
        client = MagicMock()
        (
            client.collection.return_value
            .where.return_value
            .order_by.return_value
            .stream.return_value
        ) = [_fake_doc(raw)]

        with patch("src.routes.sessions.firestore_client.get_client", return_value=client):
            result = _load_transcript("s1")

        assert result == [{"role": "assistant", "speaker_id": "alice", "transcript": "Hello!"}]


class TestGenerateReviewRobustness:
    def _fake_model(self, captured: dict) -> MagicMock:
        model = MagicMock()

        def fake_generate_content(prompt, generation_config=None):
            captured["prompt"] = prompt
            response = MagicMock()
            response.text = ReviewResult(
                summary="ok", score_communication=40, score_language=40, score_total=80
            ).model_dump_json()
            return response

        model.generate_content.side_effect = fake_generate_content
        return model

    def test_datetime_in_transcript_does_not_break_review(self):
        captured: dict = {}
        with (
            patch("src.services.gemini_client._ensure_init"),
            patch(
                "src.services.gemini_client.GenerativeModel",
                return_value=self._fake_model(captured),
            ),
        ):
            result = generate_review([
                {
                    "role": "user",
                    "transcript": "Hi!",
                    "created_at": datetime(2026, 7, 15, tzinfo=timezone.utc),
                }
            ])

        assert result.score_total == 80  # not the fallback
        assert "2026-07-15" in captured["prompt"]

    def test_fallback_on_model_error(self):
        model = MagicMock()
        model.generate_content.side_effect = RuntimeError("boom")
        with (
            patch("src.services.gemini_client._ensure_init"),
            patch("src.services.gemini_client.GenerativeModel", return_value=model),
        ):
            result = generate_review([{"role": "user", "transcript": "Hi!"}])

        assert result.summary == "Review generation is temporarily unavailable."
        assert result.score_total == 0
