# UnityCommunityNftBot — TODO

> Auto-generated from [`PLAN.md`](PLAN.md). Check off tasks as they're completed.

---

## Phase 0 · Foundations

**Exit criteria:** Bot & backend boot, DB migrations run.

- [x] Scaffold repo directories: `bot/`, `backend/`, `contracts/`, `web/miniapp/`, `web/admin/`, `tests/`
- [x] Create `.env.example` with all required vars (bot token, admin key, TonAPI key, deployer mnemonic)
- [x] Set up Python project: `requirements.txt` with python-telegram-bot, Flask, SQLAlchemy, pytoniq
- [x] **🔖 git commit: project scaffold + env + dependencies**
- [x] Create `backend/db/` — SQLAlchemy models (users, badge_types, events, attendees, assignments)
- [x] Create `backend/db/session.py` — database session + init
- [x] Run DB migrations (SQLAlchemy create_all)
- [x] **🔖 git commit: database models + migrations**
- [x] Create `bot/main.py` — minimal python-telegram-bot that boots
- [x] Create `backend/main.py` — minimal Flask app that boots
- [x] Verify bot imports and boots
- [x] Verify Flask app imports and serves health check + DB init
- [x] **🔖 git commit: bot + backend boot (Phase 0 complete ✓)**

---

## Phase 1 · Contracts

**Exit criteria:** Both contracts deploy on **testnet**, mint verified in explorer.

- [ ] Set up Tact project structure in `contracts/`
- [ ] Write transferable badge collection contract (TEP-62 NFT)
- [ ] Write soulbound badge collection contract (TEP-85 SBT)
- [ ] Write unit tests for both contracts (Tact test framework)
- [ ] Compile contracts to `contracts/build/`
- [ ] **🔖 git commit: smart contracts + tests**
- [ ] Create Python deploy scripts in `contracts/deploy/` (testnet)
- [ ] Deploy transferable collection to TON testnet
- [ ] Deploy soulbound collection to TON testnet
- [ ] Verify mint works on testnet via explorer (manual or scripted)
- [ ] **🔖 git commit: deploy scripts + testnet verification (Phase 1 complete ✓)**

---

## Phase 2 · Bot Onboarding

**Exit criteria:** Phone captured; user record in SQLite.

- [ ] Implement `/start` handler — welcome message + request_contact keyboard button
- [ ] Implement phone contact handler — create/update user record (telegram_id, phone)
- [ ] Add wallet-link prompt after phone capture (link to Mini App)
- [ ] Write tests for user creation flow
- [ ] **🔖 git commit: bot onboarding handlers + tests**
- [ ] End-to-end test: bot → /start → share phone → user in SQLite
- [ ] **🔖 git commit: bot onboarding verified (Phase 2 complete ✓)**

---

## Phase 3 · Mini App

**Exit criteria:** User links wallet; address persisted; gallery shows owned badges.

- [ ] Scaffold Mini App: Vite + React + `@tonconnect/ui-react`
- [ ] Implement TON Connect — wallet connection UI
- [ ] **🔖 git commit: mini app scaffold + TON Connect UI**
- [ ] Implement `initData` verification on backend (HMAC with bot token)
- [ ] Create `backend/api/mini_app.py` — wallet link endpoint, badge gallery endpoint
- [ ] Persist wallet address + connected_at in users table
- [ ] Build badge gallery UI (owned badges from contract)
- [ ] **🔖 git commit: mini app wallet link + gallery backend**
- [ ] End-to-end test: open Mini App → connect wallet → address stored → gallery loads
- [ ] **🔖 git commit: mini app end-to-end verified (Phase 3 complete ✓)**

---

## Phase 4 · Admin + Batch Mint

**Exit criteria:** Mint 10-test-number batch end-to-end on testnet.

- [ ] Scaffold admin frontend: Vite + React
- [ ] Implement badge type CRUD (name, description, artwork, transferable/soulbound)
- [ ] Implement event CRUD (name, description, date, assign badge type)
- [ ] Implement CSV upload / paste phone numbers for batch
- [ ] Create `backend/api/admin.py` — badge/event CRUD endpoints
- [ ] **🔖 git commit: admin dashboard + CRUD APIs**
- [ ] Build `backend/services/ton.py` — collection deploy trigger, TonAPI read calls
- [ ] Build `backend/services/mint.py` — mint logic via pytoniq
- [ ] Build `backend/worker.py` — background mint queue (asyncio task)
- [ ] Implement assignment status tracking (pending → queued → minting → minted | failed | needs_wallet)
- [ ] Implement Telegram notifications on mint success/failure
- [ ] Integrate TonAPI (choose provider, set up key, wire up read calls)
- [ ] **🔖 git commit: mint pipeline + notifications**
- [ ] End-to-end test: admin creates badge & event → uploads 10 phone numbers → batch mint → all 10 minted on testnet
- [ ] **🔖 git commit: batch mint verified (Phase 4 complete ✓)**

---

## Phase 5 · Hardening

**Exit criteria:** Runbook for going live.

- [ ] Implement mint retry logic (exponential backoff, max retries)
- [ ] Add error alerting (logs, optional Telegram alerts to admin)
- [ ] Implement admin authentication (login flow for web dashboard)
- [ ] **🔖 git commit: retries + error handling + admin auth**
- [ ] Mainnet deployment checklist (contract re-deploy to mainnet, env updates)
- [ ] Review and harden `.gitignore` for secrets
- [ ] Write full `README.md` with setup instructions and runbook
- [ ] **🔖 git commit: mainnet checklist + README + runbook**
- [ ] Final end-to-end walkthrough on testnet (all flows)
- [ ] Presentation prep — demo script, screenshots, key talking points
- [ ] **🔖 git commit: final polish (Phase 5 complete ✓)**

---

## Status

| Phase | Status |
|-------|--------|
| 0 · Foundations | ✅ Complete |
| 1 · Contracts | ⬜ Not started |
| 2 · Bot Onboarding | ⬜ Not started |
| 3 · Mini App | ⬜ Not started |
| 4 · Admin + Batch Mint | ⬜ Not started |
| 5 · Hardening | ⬜ Not started |
