# Deploy scripts

Deploys the badge collection contracts to TON (testnet by default) using the
same `PytoniqTONClient` the mint worker uses.

## Prerequisites

- `pip install -r requirements.txt` (repo root) — for `pytoniq` + `dotenv`
- `.env` at the repo root with:
  - `DEPLOYER_MNEMONIC` — 24-word mnemonic of the deployer hot wallet
  - `TON_NETWORK=testnet` (default) — or `mainnet`
- The contracts must be compiled first:

  ```bash
  cd contracts && npm run build   # produces contracts/build/*.code.boc
  ```

- The deployer wallet needs testnet TON for storage/gas (use the testnet
  faucet if it's empty).

## Usage

```bash
# From the repo root
python contracts/deploy/deploy_collection.py transferable \
    --owner EQ... --content "ipfs://collection.json"

python contracts/deploy/deploy_collection.py soulbound \
    --owner EQ... --content "ipfs://soulbound.json"
```

Options:

| Flag | Meaning |
|---|---|
| `--owner` | Collection owner address (usually the deployer wallet itself) |
| `--content` | Off-chain collection content URI (TEP-64) |
| `--network` | `testnet` (default) or `mainnet` |
| `--amount` | nanoTON attached for deployment (default 0.05 TON) |
| `--no-save` | Don't write `deployed.json` |

## Output

Prints the deployer wallet, the deployed **contract address**, and the
**deploy tx hash**. Addresses are also saved to `contracts/deploy/deployed.json`:

```json
{
  "transferable": { "address": "EQ...", "tx_hash": "ab12...", "network": "testnet", ... },
  "soulbound": { "address": "EQ...", "tx_hash": "cd34...", "network": "testnet", ... }
}
```

## Next steps

Once a collection is deployed, set the address on the badge type via the admin
API (`PUT /admin/badge-types/<id>` with `collection_address`) and run the mint
worker.
