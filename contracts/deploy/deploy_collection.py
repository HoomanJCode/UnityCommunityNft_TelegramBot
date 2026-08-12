"""Deploy a badge collection contract to TON (testnet by default).

Usage (from the repo root):

    python contracts/deploy/deploy_collection.py transferable \
        --owner EQ... --content "ipfs://collection.json"

    python contracts/deploy/deploy_collection.py soulbound \
        --owner EQ... --content "ipfs://soulbound.json"

Requires `.env` with:
    DEPLOYER_MNEMONIC  — 24-word mnemonic of the deployer/minting hot wallet
    TON_NETWORK        — "testnet" (default) or "mainnet"

The resulting contract address is saved to contracts/deploy/deployed.json so
later steps (setting `collection_address` on a badge type, minting) can use it.
"""

import argparse
import asyncio
import json
import os
import sys

# Make the repo root importable so `backend.services.ton` resolves when this
# file is run directly (sys.path[0] otherwise points at contracts/deploy/).
REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.services.ton import PytoniqTONClient  # noqa: E402

from contracts.deploy.common import (  # noqa: E402
    COLLECTIONS,
    build_collection_data,
    load_collection_code,
)

DEPLOY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deployed.json")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy a badge collection to TON")
    parser.add_argument(
        "kind",
        choices=sorted(COLLECTIONS),
        help="transferable (TEP-62) or soulbound (TEP-85)",
    )
    parser.add_argument("--owner", required=True, help="collection owner address")
    parser.add_argument(
        "--content",
        required=True,
        help="off-chain collection content URI (e.g. ipfs://...)",
    )
    parser.add_argument(
        "--network",
        default=os.getenv("TON_NETWORK", "testnet"),
        choices=["testnet", "mainnet"],
    )
    parser.add_argument(
        "--amount",
        type=int,
        default=int(0.05 * 10**9),
        help="TON (nanoTON) to attach for deployment",
    )
    parser.add_argument("--no-save", action="store_true", help="skip deployed.json")
    args = parser.parse_args()

    client = PytoniqTONClient(
        mnemonic=os.getenv("DEPLOYER_MNEMONIC", ""),
        network=args.network,
    )
    try:
        await client.connect()
        print(f"deployer wallet: {client.wallet_address}")

        code = load_collection_code(args.kind)
        data = build_collection_data(args.owner, args.content)
        address, tx_hash = await client.deploy_contract(
            code, data, amount_nanoton=args.amount
        )

        print(f"collection: {COLLECTIONS[args.kind]['contract']} ({args.kind})")
        print(f"address:    {address}")
        print(f"deploy tx:  {tx_hash}")

        if not args.no_save:
            payload = {}
            if os.path.exists(DEPLOY_FILE):
                with open(DEPLOY_FILE) as f:
                    payload = json.load(f)
            payload[args.kind] = {
                "address": address,
                "tx_hash": tx_hash,
                "network": args.network,
                "owner": args.owner,
                "content": args.content,
            }
            with open(DEPLOY_FILE, "w") as f:
                json.dump(payload, f, indent=2)
            print(f"saved to:  {DEPLOY_FILE}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
