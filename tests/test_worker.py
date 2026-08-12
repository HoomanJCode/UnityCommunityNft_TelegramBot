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

    async def mint_nft(self, collection_address: str, recipient_wallet: str) -> str:
        self.calls.append((collection_address, recipient_wallet))
        if self.fail:
            raise RuntimeError("mint boom")
        return "tx-abc123"


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


def _seed_queued(db, *, wallet="EQD...", collection="EQAbc...", status=STATUS_QUEUED):
    db.add(BadgeType(id=1, name="B", collection_address=collection))
    db.add(User(id=1, telegram_id=1, wallet_address=wallet))
    db.add(Assignment(id=1, badge_type_id=1, user_id=1, status=status))
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


def test_process_one_records_mint_error(db):
    _seed_queued(db)
    worker = MintWorker(FakeTONClient(fail=True))

    result = asyncio.run(worker.process_one(1))

    assert result == STATUS_FAILED
    a = db.get(Assignment, 1)
    assert a.status == STATUS_FAILED
    assert a.error == "mint boom"


def test_process_one_skips_non_queued(db):
    _seed_queued(db, status="pending")
    worker = MintWorker(FakeTONClient())

    result = asyncio.run(worker.process_one(1))

    assert result == "pending"
    assert db.get(Assignment, 1).status == "pending"
