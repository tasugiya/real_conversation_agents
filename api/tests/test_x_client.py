"""Tests for x_client.get_trends' 30-minute trend cache (TODO.md P1 #11).

No real HTTP calls -- httpx.AsyncClient is mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.services.x_client as x_client


@pytest.fixture(autouse=True)
def _clear_cache():
    x_client._trend_cache.clear()
    yield
    x_client._trend_cache.clear()


def _fake_response(items: list[dict]):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"data": items}
    return resp


class TestGetTrendsCache:
    @pytest.mark.asyncio
    async def test_second_call_within_ttl_does_not_hit_api(self):
        fake_client = MagicMock()
        fake_client.get = AsyncMock(return_value=_fake_response([{"trend_name": "AI"}]))
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.x_client._get_bearer_token", return_value="token"), \
             patch("src.services.x_client.httpx.AsyncClient", return_value=fake_client):
            first = await x_client.get_trends(woeid=1, environment="dev")
            second = await x_client.get_trends(woeid=1, environment="dev")

        assert first == second
        assert fake_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_different_woeid_is_not_cached_together(self):
        fake_client = MagicMock()
        fake_client.get = AsyncMock(return_value=_fake_response([{"trend_name": "AI"}]))
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.x_client._get_bearer_token", return_value="token"), \
             patch("src.services.x_client.httpx.AsyncClient", return_value=fake_client):
            await x_client.get_trends(woeid=1, environment="dev")
            await x_client.get_trends(woeid=2, environment="dev")

        assert fake_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_expired_cache_entry_refetches(self):
        fake_client = MagicMock()
        fake_client.get = AsyncMock(return_value=_fake_response([{"trend_name": "AI"}]))
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.x_client._get_bearer_token", return_value="token"), \
             patch("src.services.x_client.httpx.AsyncClient", return_value=fake_client), \
             patch("src.services.x_client.time.monotonic", side_effect=[0.0, 10_000.0]):
            await x_client.get_trends(woeid=1, environment="dev")
            await x_client.get_trends(woeid=1, environment="dev")

        assert fake_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_missing_token_is_not_cached(self):
        with patch("src.services.x_client._get_bearer_token", return_value=None):
            first = await x_client.get_trends(woeid=1, environment="dev")
        assert first == []
        assert 1 not in x_client._trend_cache

    @pytest.mark.asyncio
    async def test_failed_call_is_not_cached(self):
        fake_client = MagicMock()
        fake_client.get = AsyncMock(side_effect=Exception("timeout"))
        fake_client.__aenter__ = AsyncMock(return_value=fake_client)
        fake_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.x_client._get_bearer_token", return_value="token"), \
             patch("src.services.x_client.httpx.AsyncClient", return_value=fake_client):
            first = await x_client.get_trends(woeid=1, environment="dev")
        assert first == []
        assert 1 not in x_client._trend_cache
