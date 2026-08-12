"""Mint worker — consumes the assignment queue and mints badges on TON.

The actual TON interaction is behind a pluggable `TONClient` interface so the
queue logic is testable without a live blockchain connection. A real
pytoniq-based client can be dropped in later (see services/ton.py).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Protocol

from backend.db.models import Assignment, BadgeType, User
from backend.db.session import SessionLocal
from backend.services.assignment import (
    STATUS_FAILED,
    STATUS_MINTED,
    STATUS_MINTING,
    STATUS_NEEDS_WALLET,
    STATUS_QUEUED,
    transition_assignment,
)

logger = logging.getLogger(__name__)


class TONClient(Protocol):
    """Minimal interface for minting an NFT on TON."""

    async def mint_nft(self, collection_address: str, recipient_wallet: str) -> str:
        """Mint one NFT to the recipient wallet; return the tx hash."""
        ...


class MintWorker:
    """Polls the assignment queue and mints badges via a TON client."""

    def __init__(self, ton_client: TONClient) -> None:
        self.ton_client = ton_client

    async def process_one(self, assignment_id: int) -> str:
        """Process a single assignment; returns its final status."""
        with SessionLocal() as db:
            assignment = db.get(Assignment, assignment_id)
            if assignment is None:
                return "not_found"

            if assignment.status != STATUS_QUEUED:
                logger.warning(
                    "assignment %s not queued (status=%s), skipping",
                    assignment_id,
                    assignment.status,
                )
                return assignment.status

            user = db.get(User, assignment.user_id)
            badge_type = db.get(BadgeType, assignment.badge_type_id)

            # Missing wallet → can't mint
            if user is None or not user.wallet_address:
                assignment.status = STATUS_NEEDS_WALLET
                db.commit()
                return STATUS_NEEDS_WALLET

            if badge_type is None or not badge_type.collection_address:
                assignment.error = "badge type not deployed (no collection_address)"
                assignment.status = STATUS_FAILED
                db.commit()
                return STATUS_FAILED

            transition_assignment(assignment, STATUS_MINTING)
            db.commit()
            wallet = user.wallet_address
            collection = badge_type.collection_address

        # Mint outside the DB session (network I/O)
        try:
            tx_hash = await self.ton_client.mint_nft(collection, wallet)
        except Exception as e:  # noqa: BLE001 - record any mint failure
            with SessionLocal() as db:
                assignment = db.get(Assignment, assignment_id)
                assignment.error = str(e)
                transition_assignment(assignment, STATUS_FAILED)
                db.commit()
            logger.exception("mint failed for assignment %s", assignment_id)
            return STATUS_FAILED

        with SessionLocal() as db:
            assignment = db.get(Assignment, assignment_id)
            assignment.tx_hash = tx_hash
            assignment.minted_at = datetime.now(timezone.utc)
            transition_assignment(assignment, STATUS_MINTED)
            db.commit()
        return STATUS_MINTED

    async def run_loop(self, poll_interval: float = 5.0) -> None:
        """Continuously poll for queued assignments and process them."""
        logger.info("mint worker started")
        while True:
            try:
                with SessionLocal() as db:
                    queued = (
                        db.query(Assignment)
                        .filter(Assignment.status == STATUS_QUEUED)
                        .order_by(Assignment.id)
                        .limit(10)
                        .all()
                    )
                    ids = [a.id for a in queued]

                for aid in ids:
                    await self.process_one(aid)
            except Exception:  # noqa: BLE001
                logger.exception("worker iteration failed")

            await asyncio.sleep(poll_interval)
