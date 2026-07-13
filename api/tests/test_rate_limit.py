"""Tests for rate_limiter's per-category bucket separation (BUG-021 fix).

Covers: same IP + different categories don't share quota, same IP + same
category still enforces the limit, and the 429's Retry-After header. No
real HTTP/network calls -- Request is faked with a minimal object carrying
.client.host.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from src.middleware.rate_limit import _hits, rate_limiter


def _fake_request(ip: str = "1.2.3.4") -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host=ip))


@pytest.fixture(autouse=True)
def _clear_hits():
    _hits.clear()
    yield
    _hits.clear()


class TestRateLimiterCategorySeparation:
    @pytest.mark.asyncio
    async def test_different_categories_do_not_share_quota(self):
        with patch("src.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(rate_limit_per_ip_per_minute=1)
            # "session_setup" carries no category multiplier, unlike
            # stream_ticket (3x) -- keeps this test's limit exactly 1/min.
            session_setup = rate_limiter("session_setup")
            review = rate_limiter("review")
            request = _fake_request()

            await session_setup(request)
            # A second session_setup hit is over the limit (1/min)...
            with pytest.raises(HTTPException) as exc_info:
                await session_setup(request)
            assert exc_info.value.status_code == 429

            # ...but "review" is a separate bucket for the same IP, so it's
            # still fresh -- this is the exact scenario that starved
            # end_session/retry_review before the fix.
            await review(request)

    @pytest.mark.asyncio
    async def test_same_category_enforces_limit(self):
        with patch("src.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(rate_limit_per_ip_per_minute=2)
            review = rate_limiter("review")
            request = _fake_request()

            await review(request)
            await review(request)
            with pytest.raises(HTTPException) as exc_info:
                await review(request)
            assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_different_ips_do_not_share_quota(self):
        with patch("src.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(rate_limit_per_ip_per_minute=1)
            review = rate_limiter("review")

            await review(_fake_request("1.1.1.1"))
            await review(_fake_request("2.2.2.2"))  # different IP, same category -- fine

    @pytest.mark.asyncio
    async def test_429_includes_retry_after_header(self):
        with patch("src.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(rate_limit_per_ip_per_minute=1)
            auth = rate_limiter("auth")
            request = _fake_request()

            await auth(request)
            with pytest.raises(HTTPException) as exc_info:
                await auth(request)
            assert "Retry-After" in exc_info.value.headers


class TestRateLimiterCategoryMultipliers:
    @pytest.mark.asyncio
    async def test_auth_is_tighter_than_base(self):
        """auth halves the base limit (rounded down) to slow password guessing."""
        with patch("src.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(rate_limit_per_ip_per_minute=10)
            auth = rate_limiter("auth")
            request = _fake_request()

            for _ in range(5):
                await auth(request)
            with pytest.raises(HTTPException):
                await auth(request)

    @pytest.mark.asyncio
    async def test_stream_ticket_is_looser_than_base(self):
        """stream_ticket triples the base limit so flaky reconnects aren't punished."""
        with patch("src.middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(rate_limit_per_ip_per_minute=10)
            stream_ticket = rate_limiter("stream_ticket")
            request = _fake_request()

            for _ in range(30):
                await stream_ticket(request)
            with pytest.raises(HTTPException):
                await stream_ticket(request)
