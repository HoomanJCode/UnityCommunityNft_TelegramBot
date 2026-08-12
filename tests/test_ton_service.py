"""Tests for the pytoniq-backed TON client (no network required)."""

import asyncio

from pytoniq import Address, begin_cell

from backend.services.ton import (
    ITEM_AMOUNT_NANOTON,
    MINT_OP,
    MINT_VALUE_NANOTON,
    OFFCHAIN_CONTENT_PREFIX,
    PytoniqTONClient,
    from_env,
)


def _fake_addr(byte: str = "11") -> str:
    """Return a valid bounceable-off address derived from a raw form."""
    return Address(f"0:{byte * 32}").to_str(is_bounceable=False)


class FakeProvider:
    def __init__(self, next_index: int = 0):
        self.next_index = next_index
        self.started = False
        self.closed = False
        self.get_calls = []

    async def start_up(self):
        self.started = True

    async def close_all(self):
        self.closed = True

    async def run_get_method(self, address, method, stack):
        self.get_calls.append((address, method, stack))
        return [self.next_index, "content-cell", "owner-slice"]


class FakeWallet:
    def __init__(self, uninitialized: bool = False):
        self.address = Address(f"0:{'22' * 32}")
        self.private_key = b"\x01" * 32
        self.wallet_id = 698983191
        self._uninitialized = uninitialized
        self.seqno_value = 0
        self.init_sent = False
        self.sent = []
        self.last_messages = []

    @property
    def is_uninitialized(self):
        return self._uninitialized

    async def send_init_external(self):
        self.init_sent = True
        self.seqno_value = 1

    async def get_seqno(self):
        return self.seqno_value

    def create_wallet_internal_message(self, destination, value, body, **kwargs):
        return {"destination": destination, "value": value, "body": body}

    def raw_create_transfer_msg(self, private_key, seqno, wallet_id, messages):
        self.last_messages = messages
        return begin_cell().store_uint(seqno, 32).end_cell()

    async def send_external(self, body):
        self.sent.append(body)


def _parse_mint_body(body):
    s = body.begin_parse()
    content = s.load_ref().begin_parse()
    return {
        "op": s.load_uint(32),
        "query_id": s.load_uint(64),
        "index": s.load_uint(64),
        "amount": s.load_coins(),
        "owner": s.load_address().to_str(is_bounceable=False),
        "forward_payload": s.load_ref(),
        "content_prefix": content.load_uint(8),
        "uri": content.load_string(),
    }


def _client(provider=None, wallet=None, **kwargs):
    return PytoniqTONClient(
        mnemonic=["word"] * 24,
        provider=provider,
        wallet=wallet,
        init_poll_attempts=3,
        init_poll_interval=0.01,
        **kwargs,
    )


def test_mint_nft_submits_transfer_and_returns_hash():
    provider = FakeProvider(next_index=7)
    wallet = FakeWallet()
    client = _client(provider=provider, wallet=wallet)
    collection = _fake_addr("ab")
    owner = _fake_addr("cd")

    tx_hash = asyncio.run(
        client.mint_nft(collection, owner, "ipfs://meta.json")
    )

    # hash is the hash of the exact cell that was sent
    assert len(tx_hash) == 64
    assert tx_hash == wallet.sent[0].hash.hex()
    # collection data queried for the next item index
    assert provider.get_calls == [(collection, "get_collection_data", [])]

    # wallet message built with the mint body and full value
    message = wallet.last_messages[0]
    assert message["destination"].to_str(is_bounceable=False) == collection
    assert message["value"] == MINT_VALUE_NANOTON

    parsed = _parse_mint_body(message["body"])
    assert parsed["op"] == MINT_OP
    assert parsed["query_id"] == 0
    assert parsed["index"] == 7
    assert parsed["amount"] == ITEM_AMOUNT_NANOTON
    assert parsed["owner"] == owner
    assert parsed["content_prefix"] == OFFCHAIN_CONTENT_PREFIX
    assert parsed["uri"] == "ipfs://meta.json"


def test_mint_nft_deploys_wallet_first_when_uninitialized():
    provider = FakeProvider()
    wallet = FakeWallet(uninitialized=True)
    client = _client(provider=provider, wallet=wallet)

    asyncio.run(client.mint_nft(_fake_addr(), _fake_addr("ee")))

    assert wallet.init_sent is True
    assert wallet.sent  # transfer sent after init
    assert wallet.seqno_value >= 1


def test_mint_nft_uses_metadata_uri_fallback():
    provider = FakeProvider()
    wallet = FakeWallet()
    client = _client(
        provider=provider, wallet=wallet, metadata_uri="ipfs://fallback.json"
    )

    asyncio.run(client.mint_nft(_fake_addr(), _fake_addr("ef")))

    parsed = _parse_mint_body(wallet.last_messages[0]["body"])
    assert parsed["uri"] == "ipfs://fallback.json"


def test_mint_nft_item_uri_overrides_metadata_uri():
    provider = FakeProvider()
    wallet = FakeWallet()
    client = _client(
        provider=provider, wallet=wallet, metadata_uri="ipfs://fallback.json"
    )

    asyncio.run(
        client.mint_nft(_fake_addr(), _fake_addr("ef"), "ipfs://override.json")
    )

    parsed = _parse_mint_body(wallet.last_messages[0]["body"])
    assert parsed["uri"] == "ipfs://override.json"


def test_connect_with_injected_wallet_is_idempotent():
    provider = FakeProvider()
    wallet = FakeWallet()
    client = _client(provider=provider, wallet=wallet)

    asyncio.run(client.connect())

    assert provider.started is False
    assert client.wallet is wallet


def test_wallet_address_before_and_after_connect():
    provider = FakeProvider()
    wallet = FakeWallet()
    client = _client(provider=provider, wallet=wallet)

    assert client.wallet_address is None

    asyncio.run(client.connect())
    assert client.wallet_address == wallet.address.to_str(is_bounceable=False)


def test_close_closes_provider():
    provider = FakeProvider()
    wallet = FakeWallet()
    client = _client(provider=provider, wallet=wallet)

    asyncio.run(client.connect())
    asyncio.run(client.close())

    assert provider.closed is True


def test_from_env(monkeypatch):
    monkeypatch.setenv("DEPLOYER_MNEMONIC", "alpha beta gamma")
    monkeypatch.setenv("TON_NETWORK", "mainnet")

    client = from_env()

    assert client.mnemonic == ["alpha", "beta", "gamma"]
    assert client.network == "mainnet"


def test_from_env_defaults_to_testnet(monkeypatch):
    monkeypatch.setenv("DEPLOYER_MNEMONIC", "alpha beta gamma")
    monkeypatch.delenv("TON_NETWORK", raising=False)

    client = from_env()

    assert client.network == "testnet"


def test_from_env_missing_mnemonic_raises(monkeypatch):
    import pytest

    monkeypatch.delenv("DEPLOYER_MNEMONIC", raising=False)

    with pytest.raises(ValueError):
        from_env()


def test_unknown_network_raises():
    import pytest

    with pytest.raises(ValueError):
        PytoniqTONClient(mnemonic=["word"] * 24, network="moonnet")
