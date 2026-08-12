"""Tests for the mint worker."""

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.worker as worker_mod
from backend.db.models import Assignment, BadgeType, Base, User
from backend.services.assignment import (
    STATUS_FAILED,
    STATUS_MINTED,
    STATUS_NEEDS_WALLET,
    STATUS_QUEUED,
)
from backend.worker import MintWorker


class FakeTONClient:
    """Records calls and returns a fixed tx hash (or raises)."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls = []

    async def mint_nft(
        self, collection_address: str, recipient_wallet: str, item_uri: str | None = None
    ) -> str:
        self.calls.append((collection_address, recipient_wallet))
        if self.fail:
            raise RuntimeError("mint boom")
        return "tx-abc123"


class FakeNotifier:
    """Records notification + admin-alert calls."""

    def __init__(self):
        self.messages = []
        self.alerts = []

    async def notify(self, telegram_id: int, text: str) -> None:
        self.messages.append((telegram_id, text))

    async def alert_admin(self, text: str) -> None:
        self.alerts.append(text)


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(worker_mod, "SessionLocal", Session)
    return Session()


def _seed_queued(
    db,
    *,
    wallet="EQD...",
    collection="EQAbc...",
    status=STATUS_QUEUED,
    retry_count=0,
):
    db.add(BadgeType(id=1, name="B", collection_address=collection))
    db.add(User(id=1, telegram_id=1, wallet_address=wallet))
    db.add(
        Assignment(
            id=1,
            badge_type_id=1,
            user_id=1,
            status=status,
            retry_count=retry_count,
        )
    )
    db.commit()


def test_process_one_mints_successfully(db):
    _seed_queued(db)
    client = FakeTONClient()
    worker = MintWorker(client)

    result = asyncio.run(worker.process_one(1))

    assert result == STATUS_MINTED
    assert client.calls == [("EQAbc...", "EQD...")]
    a = db.get(Assignment, 1)
    assert a.status == STATUS_MINTED
    assert a.tx_hash == "tx-abc123"
    assert a.minted_at is not None


def test_process_one_needs_wallet(db):
    _seed_queued(db, wallet=None)
    worker = MintWorker(FakeTONClient())

    result = asyncio.run(worker.process_one(1))

    assert result == STATUS_NEEDS_WALLET
    assert db.get(Assignment, 1).status == STATUS_NEEDS_WALLET


def test_process_one_fails_when_no_collection(db):
    _seed_queued(db, collection=None)
    worker = MintWorker(FakeTONClient())

    result = asyncio.run(worker.process_one(1))

    assert result == STATUS_FAILED
    a = db.get(Assignment, 1)
    assert a.status == STATUS_FAILED
    assert "collection" in a.error


def test_process_one_retries_after_failure(db):
    _seed_queued(db)
    worker = MintWorker(FakeTONClient(fail=True))

    result = asyncio.run(worker.process_one(1))

    # First failure → re-queued for retry
    assert result == STATUS_QUEUED
    a = db.get(Assignment, 1)
    assert a.status == STATUS_QUEUED
    assert a.retry_count == 1
    assert a.error == "mint boom"


def test_process_one_gives_up_after_max_retries(db):
    from backend.worker import MAX_RETRIES

    _seed_queued(db, retry_count=MAX_RETRIES - 1)
    worker = MintWorker(FakeTONClient(fail=True))

    result = asyncio.run(worker.process_one(1))

    assert result == STATUS_FAILED
    a = db.get(Assignment, 1)
    assert a.status == STATUS_FAILED
    assert a.retry_count == MAX_RETRIES


def test_process_one_notifies_on_success(db):
    _seed_queued(db)
    notifier = FakeNotifier()
    worker = MintWorker(FakeTONClient(), notifier=notifier)

    asyncio.run(worker.process_one(1))

    assert len(notifier.messages) == 1
    telegram_id, text = notifier.messages[0]
    assert telegram_id == 1
    assert "minted" in text


def test_process_one_notifies_on_final_failure(db):
    from backend.worker import MAX_RETRIES

    _seed_queued(db, retry_count=MAX_RETRIES - 1)  # this attempt is the last
    notifier = FakeNotifier()
    worker = MintWorker(FakeTONClient(fail=True), notifier=notifier)

    asyncio.run(worker.process_one(1))

    assert len(notifier.messages) == 1
    telegram_id, text = notifier.messages[0]
    assert telegram_id == 1
    assert "failed" in text


def test_process_one_does_not_notify_on_retry(db):
    notifier = FakeNotifier()
    worker = MintWorker(FakeTONClient(fail=True), notifier=notifier)

    _seed_queued(db)
    asyncio.run(worker.process_one(1))

    # Re-queued for retry → no notification yet
    assert notifier.messages == []
    assert notifier.alerts == []


def test_process_one_alerts_admin_on_final_failure(db):
    from backend.worker import MAX_RETRIES

    _seed_queued(db, retry_count=MAX_RETRIES - 1)  # this attempt is the last
    notifier = FakeNotifier()
    worker = MintWorker(FakeTONClient(fail=True), notifier=notifier)

    asyncio.run(worker.process_one(1))

    # The user gets the failure notice AND the operator gets an admin alert.
    assert len(notifier.messages) == 1
    assert len(notifier.alerts) == 1
    assert "failed" in notifier.alerts[0].lower()


def test_process_one_skips_non_queued(db):
    _seed_queued(db, status="pending")
    worker = MintWorker(FakeTONClient())

    result = asyncio.run(worker.process_one(1))

    assert result == "pending"
    assert db.get(Assignment, 1).status == "pending"
