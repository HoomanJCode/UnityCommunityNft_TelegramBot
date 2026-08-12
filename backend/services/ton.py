"""TON service — real blockchain client backed by pytoniq.

Implements the `TONClient` protocol (see `backend/worker.py`) using a
`WalletV4R2` derived from the deployer mnemonic, connected to the TON
network through a `LiteBalancer` (testnet or mainnet).

Minting sends a `mint` internal message (op = 1) to the collection contract
with the next item index, the item's initial balance, the recipient's wallet
address as the item owner, and the item's off-chain metadata URI.

> The demo Tact contracts (Phase 1) must parse this mint body layout:
> `op:uint32, query_id:uint64, index:uint64, amount:coins, owner:address,
> common_content:ref, forward_payload:ref`.
"""

import asyncio
import logging
import os

from pytoniq import Address, LiteBalancer, WalletV4R2, begin_cell
from pytoniq_core import Cell

from backend.worker import MintWorker
from backend.worker import TONClient  # noqa: F401  (re-export for convenience)

logger = logging.getLogger(__name__)

# TEP-62 NFT collection "mint" op code.
MINT_OP = 1
# First byte of the off-chain content cell (per TEP-64 metadata standard).
OFFCHAIN_CONTENT_PREFIX = 0x01
# Initial balance (nanoTON) attached to each newly minted NFT item.
ITEM_AMOUNT_NANOTON = 100_000_000  # 0.1 TON
# Total value (nanoTON) sent to the collection with the mint message:
# the item balance above plus gas for the collection to create the item.
MINT_VALUE_NANOTON = 150_000_000  # 0.15 TON


class PytoniqTONClient:
    """Mints NFT badges on TON via pytoniq.

    A real provider and wallet are created lazily on first use. Both can be
    injected for tests (see `tests/test_ton_service.py`).
    """

    def __init__(
        self,
        mnemonic: str | list[str],
        network: str = "testnet",
        provider=None,
        wallet=None,
        metadata_uri: str | None = None,
        init_poll_attempts: int = 10,
        init_poll_interval: float = 1.0,
    ) -> None:
        self.mnemonic = mnemonic.split() if isinstance(mnemonic, str) else list(mnemonic)
        self.network = network.lower()
        if self.network not in ("testnet", "mainnet"):
            raise ValueError(f"unknown TON network: {network!r} (expected 'testnet' or 'mainnet')")

        # Injectable for tests.
        self._provider = provider
        self._wallet = wallet
        self._metadata_uri = metadata_uri

        self._init_poll_attempts = init_poll_attempts
        self._init_poll_interval = init_poll_interval
        self._lock = asyncio.Lock()
        self._closed = False
        self._connected = False

    @property
    def provider(self):
        """The connected LiteClient/LiteBalancer (None until connected)."""
        return self._provider

    @property
    def wallet(self):
        """The loaded wallet (None until connected)."""
        return self._wallet

    @property
    def wallet_address(self) -> str | None:
        """The wallet address (raw form) once connected, else None."""
        if not self._connected or self._wallet is None:
            return None
        return self._wallet.address.to_str(is_bounceable=False)

    async def connect(self) -> None:
        """Connect to the network and load the deployer wallet (idempotent)."""
        if self._closed:
            raise RuntimeError("PytoniqTONClient is closed")
        if self._connected:
            return

        if self._wallet is None:
            if self._provider is None:
                if self.network == "mainnet":
                    self._provider = LiteBalancer.from_mainnet_config()
                else:
                    self._provider = LiteBalancer.from_testnet_config()
            await self._provider.start_up()
            self._wallet = await WalletV4R2.from_mnemonic(
                self._provider, self.mnemonic
            )
        self._connected = True

    async def close(self) -> None:
        """Disconnect from the network and release resources."""
        if self._provider is not None:
            await self._provider.close_all()
        self._closed = True
        self._connected = False

    async def next_item_index(self, collection_address: str) -> int:
        """Return the next mintable item index of an NFT collection."""
        res = await self._provider.run_get_method(
            collection_address, "get_collection_data", []
        )
        return int(res[0])

    def _build_mint_body(
        self,
        item_index: int,
        owner_address: str,
        item_uri: str,
    ) -> Cell:
        """Build the `mint` message body for a demo collection contract."""
        common_content = (
            begin_cell()
            .store_uint(OFFCHAIN_CONTENT_PREFIX, 8)
            .store_string(item_uri or "")
            .end_cell()
        )
        return (
            begin_cell()
            .store_uint(MINT_OP, 32)           # op: mint
            .store_uint(0, 64)                 # query_id
            .store_uint(item_index, 64)        # item index
            .store_coins(ITEM_AMOUNT_NANOTON)  # initial item balance
            .store_address(Address(owner_address))  # item owner
            .store_ref(common_content)         # off-chain metadata URI
            .store_ref(Cell.empty())           # forward_payload
            .end_cell()
        )

    async def mint_nft(
        self,
        collection_address: str,
        recipient_wallet: str,
        item_uri: str | None = None,
    ) -> str:
        """Mint one NFT badge to `recipient_wallet`; return the tx (message) hash.

        The message hash is computed from the signed transfer cell before it is
        submitted — `raw_send_message` itself only returns a network status.
        """
        async with self._lock:
            await self.connect()
            wallet = self._wallet

            # An undeployed wallet must be activated before it can send.
            if wallet.is_uninitialized:
                await wallet.send_init_external()
                seqno = 0
                for _ in range(self._init_poll_attempts):
                    await asyncio.sleep(self._init_poll_interval)
                    seqno = await wallet.get_seqno()
                    if seqno > 0:
                        break
                if seqno == 0:
                    # Never return a hash for a transfer that cannot land.
                    raise RuntimeError(
                        "wallet activation not confirmed (seqno still 0)"
                    )

            item_index = await self.next_item_index(collection_address)
            uri = item_uri or self._metadata_uri or ""
            body = self._build_mint_body(item_index, recipient_wallet, uri)

            message = wallet.create_wallet_internal_message(
                destination=Address(collection_address),
                value=MINT_VALUE_NANOTON,
                body=body,
            )
            seqno = await wallet.get_seqno()
            transfer_cell = wallet.raw_create_transfer_msg(
                wallet.private_key, seqno, wallet.wallet_id, [message]
            )
            tx_hash = transfer_cell.hash.hex()
            status = await wallet.send_external(body=transfer_cell)
            if status not in (None, 1):
                raise RuntimeError(f"send_external failed with status {status!r}")

            logger.info(
                "mint submitted: collection=%s index=%s hash=%s",
                collection_address,
                item_index,
                tx_hash,
            )
            return tx_hash


def from_env() -> PytoniqTONClient:
    """Build a client from environment variables (see `.env.example`)."""
    mnemonic = os.getenv("DEPLOYER_MNEMONIC", "").strip()
    if not mnemonic:
        raise ValueError(
            "DEPLOYER_MNEMONIC is not set — add it to .env (see .env.example)"
        )
    return PytoniqTONClient(
        mnemonic=mnemonic,
        network=os.getenv("TON_NETWORK", "testnet"),
    )


async def run_worker(poll_interval: float = 5.0) -> None:
    """Run the mint worker with a real pytoniq client (+ Telegram notifier)."""
    client = from_env()
    notifier = None
    token = os.getenv("BOT_TOKEN")
    if token:
        from telegram import Bot

        from backend.services.notify import TelegramNotifier

        notifier = TelegramNotifier(Bot(token=token))

    worker = MintWorker(client, notifier=notifier)
    try:
        await worker.run_loop(poll_interval)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(run_worker())
