"""TON service — real blockchain client (to be implemented).

`pytoniq` (the intended TON SDK) requires the Rust-based `pytoniq-core`
extension, which cannot be built in the current environment. This module
documents the intended interface so `backend/worker.py` can depend on it
without a concrete implementation.

When pytoniq becomes available, implement `PytoniqTONClient` here and wire it
into the worker:

    from backend.services.ton import PytoniqTONClient
    from backend.worker import MintWorker

    worker = MintWorker(PytoniqTONClient(mnemonic=..., network="testnet"))
    asyncio.run(worker.run_loop())
"""

from backend.worker import TONClient  # noqa: F401  (re-export for convenience)
