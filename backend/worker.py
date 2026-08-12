"""Mint worker — consumes the assignment queue and mints badges on TON.

The actual TON interaction is behind a pluggable `TONClient` interface so the
queue logic is testable without a live blockchain connection. A real
pytoniq-based client can be dropped in later (see services/ton.py).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import update

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

# Maximum mint attempts before an assignment is marked failed permanently.
MAX_RETRIES = 3


class TONClient(Protocol):
    """Minimal interface for minting an NFT on TON."""

    async def mint_nft(
        self,
        collection_address: str,
        recipient_wallet: str,
        item_uri: str | None = None,
    ) -> str:
        """Mint one NFT to the recipient wallet; return the tx hash."""
        ...


class Notifier(Protocol):
    """Optional hook for notifying users about mint outcomes."""

    async def notify(self, telegram_id: int, text: str) -> None:
        """Send a message to the given Telegram user."""
        ...


class MintWorker:
    """Polls the assignment queue and mints badges via a TON client."""

    def __init__(
        self,
        ton_client: TONClient,
        notifier: Notifier | None = None,
    ) -> None:
        self.ton_client = ton_client
        self.notifier = notifier

    async def process_one(self, assignment_id: int) -> str:
        """Process a single assignment; returns its final status."""
        # Step 1: read the assignment and validate prerequisites.
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
                transition_assignment(assignment, STATUS_NEEDS_WALLET)
                db.commit()
                return STATUS_NEEDS_WALLET

            if badge_type is None or not badge_type.collection_address:
                assignment.error = "badge type not deployed (no collection_address)"
                transition_assignment(assignment, STATUS_FAILED)
                db.commit()
                return STATUS_FAILED

            wallet = user.wallet_address
            collection = badge_type.collection_address
            telegram_id = user.telegram_id
            badge_name = badge_type.name
            badge_uri = badge_type.metadata_uri

        # Step 2: atomically claim the assignment (queued -> minting).
        # A conditional UPDATE ensures only one worker can claim it.
        with SessionLocal() as db:
            result = db.execute(
                update(Assignment)
                .where(
                    Assignment.id == assignment_id,
                    Assignment.status == STATUS_QUEUED,
                )
                .values(status=STATUS_MINTING)
            )
            db.commit()
            if result.rowcount == 0:
                return "already_claimed"

        # Step 3: mint outside the DB session (network I/O).
        try:
            tx_hash = await self.ton_client.mint_nft(
                collection, wallet, badge_uri
            )
        except Exception as e:  # noqa: BLE001 - record any mint failure
            with SessionLocal() as db:
                assignment = db.get(Assignment, assignment_id)
                assignment.error = str(e)
                assignment.retry_count += 1
                transition_assignment(assignment, STATUS_FAILED)
                if assignment.retry_count < MAX_RETRIES:
                    # Re-queue for another attempt later.
                    transition_assignment(assignment, STATUS_QUEUED)
                db.commit()
                retry_count = assignment.retry_count
                final_status = assignment.status
            logger.warning(
                "mint failed for assignment %s (attempt %s)",
                assignment_id,
                retry_count,
            )
            # Only notify the user once we stop retrying.
            if self.notifier and final_status == STATUS_FAILED:
                await self.notifier.notify(
                    telegram_id,
                    f"❌ Minting your '{badge_name}' badge failed: {e}",
                )
            return final_status

        # Step 4: mark as minted.
        with SessionLocal() as db:
            assignment = db.get(Assignment, assignment_id)
            assignment.tx_hash = tx_hash
            assignment.minted_at = datetime.now(timezone.utc)
            assignment.error = None  # clear any stale retry error
            transition_assignment(assignment, STATUS_MINTED)
            db.commit()
        if self.notifier:
            await self.notifier.notify(
                telegram_id,
                f"🎉 Your '{badge_name}' badge was minted!\n"
                f"tx: {tx_hash}",
            )
        return STATUS_MINTED

    async def run_loop(self, poll_interval: float = 5.0) -> None:
        """Continuously poll for queued assignments and process them."""
        logger.info("mint worker started")
        while True:
            try:
                # Grab up to 10 queued jobs per tick; the atomic claim inside
                # process_one guarantees a job is never double-processed even
                # if several worker processes run at once.
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
            except Exception:  # noqa: BLE001 - a bad job must not kill the loop
                logger.exception("worker iteration failed")

            await asyncio.sleep(poll_interval)
