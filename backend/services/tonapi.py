"""TonAPI service — read-only access to TON network data via tonapi.io.

Used by the admin dashboard to *verify* on-chain state (deployed collections,
minted items, wallet balances) without spinning up a lite client. Everything
here is a thin wrapper over the TonAPI v2 REST API:

    mainnet base: https://tonapi.io
    testnet base: https://testnet.tonapi.io

Authentication uses the `Authorization: Bearer <TON_API_KEY>` header (keys are
issued via Ton Console). The key is optional — without one the client reports
`enabled == False` and callers are expected to degrade gracefully (e.g. show
"unverified" instead of failing the whole request).
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# Per-network API base URLs (see https://docs.tonapi.io).
BASE_URLS = {
    "mainnet": "https://tonapi.io",
    "testnet": "https://testnet.tonapi.io",
}


class TonAPIClient:
    """Small async wrapper around the read endpoints of the TonAPI v2 API."""

    def __init__(
        self,
        api_key: str = "",
        network: str = "testnet",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.network = network.lower()
        if self.network not in BASE_URLS:
            raise ValueError(
                f"unknown TON network: {network!r} (expected 'testnet' or 'mainnet')"
            )
        # Injectable transport for tests (httpx.MockTransport) — when absent we
        # create a real client per request to keep connection lifetimes simple.
        self._client = client

    @property
    def enabled(self) -> bool:
        """True when an API key is configured (free-tier calls require one)."""
        return bool(self.api_key)

    @property
    def base_url(self) -> str:
        return BASE_URLS[self.network]

    async def _get(self, path: str, params: dict | None = None) -> dict:
        """GET a TonAPI v2 endpoint and return the JSON body."""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        if self._client is not None:
            res = await self._client.get(
                f"{self.base_url}{path}", params=params, headers=headers
            )
        else:
            # One-shot client: fine for the low request volumes of an admin
            # dashboard, and avoids managing a shared connection pool.
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(
                    f"{self.base_url}{path}", params=params, headers=headers
                )
        res.raise_for_status()
        return res.json()

    async def get_account(self, address: str) -> dict:
        """Full account info: balance (nanoTON), status, code, etc."""
        return await self._get(f"/v2/accounts/{address}")

    async def get_balance(self, address: str) -> int:
        """Return the account balance in nanoTON (0 for unknown accounts)."""
        data = await self.get_account(address)
        try:
            return int(data.get("balance", 0))
        except (TypeError, ValueError):
            return 0

    async def get_nft_item(self, address: str) -> dict:
        """Info about a single NFT item: owner, collection, metadata, verified."""
        return await self._get(f"/v2/nfts/{address}")

    async def get_collection(self, address: str) -> dict:
        """Info about an NFT collection: metadata, owner, next_item_index."""
        return await self._get(f"/v2/nfts/collections/{address}")


def from_env() -> TonAPIClient:
    """Build a client from environment variables (see `.env.example`)."""
    return TonAPIClient(
        api_key=os.getenv("TON_API_KEY", ""),
        network=os.getenv("TON_NETWORK", "testnet"),
    )
