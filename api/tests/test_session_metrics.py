"""Tests for _compute_session_metrics (Scoring Observer).

Pure computation — no external services needed.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.routes.sessions import _compute_session_metrics


def _msg(role: str, text: str) -> dict:
    return {"role": role, "transcript": text, "speaker_id": role}


class TestComputeSessionMetrics:
    def test_empty_transcript(self):
        m = _compute_session_metrics([], None, None)
        assert m["user_utterance_count"] == 0
        assert m["ai_utterance_count"] == 0
        assert m["question_count"] == 0
        assert m["duration_seconds"] is None

    def test_counts_user_and_ai_separately(self):
        transcript = [
            _msg("user", "Hi there."),
            _msg("assistant", "Hello!"),
            _msg("user", "How are you?"),
            _msg("assistant", "I'm great."),
            _msg("assistant", "How about you?"),
        ]
        m = _compute_session_metrics(transcript, None, None)
        assert m["user_utterance_count"] == 2
        assert m["ai_utterance_count"] == 3

    def test_counts_questions_from_user_only(self):
        transcript = [
            _msg("user", "What do you think?"),
            _msg("user", "Really?"),
            _msg("assistant", "Is that so?"),  # AI question should NOT count
            _msg("user", "I agree."),  # no question mark
        ]
        m = _compute_session_metrics(transcript, None, None)
        assert m["question_count"] == 2  # only user msgs with "?"

    def test_duration_computed_correctly(self):
        now = datetime.now(timezone.utc)
        started = now - timedelta(seconds=90)
        m = _compute_session_metrics([], started, now)
        assert m["duration_seconds"] == 90

    def test_duration_is_none_if_timestamps_missing(self):
        m = _compute_session_metrics([], None, None)
        assert m["duration_seconds"] is None

    def test_question_mark_in_middle_counts(self):
        transcript = [_msg("user", "Wait, really? That's surprising.")]
        m = _compute_session_metrics(transcript, None, None)
        assert m["question_count"] == 1
