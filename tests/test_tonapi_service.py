"""Tests for the TonAPI service client (offline, via httpx MockTransport)."""

import httpx
import pytest

from backend.services.tonapi import TonAPIClient


@pytest.fixture()
def api_key(monkeypatch):
    # Make sure tests never read a real key from the environment.
    monkeypatch.delenv("TON_API_KEY", raising=False)
    monkeypatch.setenv("TON_NETWORK", "testnet")
    return "test-key"


def _client(handler, api_key="test-key"):
    transport = httpx.MockTransport(handler)
    return TonAPIClient(
        api_key=api_key,
        network="testnet",
        client=httpx.AsyncClient(transport=transport),
    )


def test_enabled_requires_key():
    assert TonAPIClient(api_key="", network="testnet").enabled is False
    assert TonAPIClient(api_key="k", network="testnet").enabled is True


def test_unknown_network_rejected():
    with pytest.raises(ValueError):
        TonAPIClient(api_key="k", network="moonnet")


@pytest.mark.asyncio
async def test_get_balance(api_key):
    def handler(request):
        # Balance is returned in nanoTON by TonAPI.
        return httpx.Response(200, json={"balance": 1_500_000_000})

    client = _client(handler, api_key)
    assert await client.get_balance("EQD...") == 1_500_000_000


@pytest.mark.asyncio
async def test_get_collection(api_key):
    def handler(request):
        assert request.url.path == "/v2/nfts/collections/EQAbc"
        return httpx.Response(
            200,
            json={
                "metadata": {"name": "VIP Club", "image": "https://x/vip.png"},
                "next_item_index": 42,
                "verified": True,
            },
        )

    client = _client(handler, api_key)
    data = await client.get_collection("EQAbc")
    assert data["metadata"]["name"] == "VIP Club"
    assert data["next_item_index"] == 42


@pytest.mark.asyncio
async def test_get_nft_item(api_key):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "owner": {"address": "EQD...owner"},
                "metadata": {"name": "Badge #1"},
                "verified": True,
            },
        )

    client = _client(handler, api_key)
    data = await client.get_nft_item("EQD...nft")
    assert data["metadata"]["name"] == "Badge #1"


@pytest.mark.asyncio
async def test_auth_header_sent(api_key):
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"balance": 0})

    client = _client(handler, api_key)
    await client.get_balance("EQD...")
    assert captured["auth"] == "Bearer test-key"
