"""Shared helpers for the collection deploy scripts.

Loads the compiled contract code from `contracts/build/` and builds the init
data cell exactly the way the Tact compiler does (see the generated TS
wrappers: `storeUint(0, 1)` init flag + init args in declaration order).
"""

import os

from dotenv import load_dotenv
from pytoniq import Address, begin_cell
from pytoniq_core import Cell

load_dotenv()

# contracts/ directory (parent of this deploy/ dir).
CONTRACTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# kind → compiled artifact paths under contracts/build/.
COLLECTIONS = {
    "transferable": {
        "code_boc": "transferable/badge_collection_BadgeCollection.code.boc",
        "contract": "BadgeCollection",
    },
    "soulbound": {
        "code_boc": "soulbound/soulbound_collection_SoulboundCollection.code.boc",
        "contract": "SoulboundCollection",
    },
}


def offchain_content(uri: str) -> Cell:
    """Build an off-chain content cell: 0x01 prefix + URI (TEP-64 style)."""
    return begin_cell().store_uint(0x01, 8).store_string(uri).end_cell()


def load_collection_code(kind: str) -> Cell:
    """Read the compiled contract code (BOC) for the given collection kind."""
    if kind not in COLLECTIONS:
        raise ValueError(
            f"unknown collection kind: {kind!r} (expected transferable|soulbound)"
        )
    path = os.path.join(CONTRACTS_DIR, "build", COLLECTIONS[kind]["code_boc"])
    with open(path, "rb") as f:
        return Cell.one_from_boc(f.read())


def build_collection_data(owner: str, content_uri: str) -> Cell:
    """Build the collection init data cell.

    Mirrors the Tact-generated layout:
        storeUint(0, 1)  — init flag
        storeAddress(owner)
        storeRef(content)  — off-chain collection content cell
    """
    return (
        begin_cell()
        .store_uint(0, 1)
        .store_address(Address(owner))
        .store_ref(offchain_content(content_uri))
        .end_cell()
    )
