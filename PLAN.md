# UnityCommunityNftBot — Project Plan

Web3 event-badge platform on Telegram: users verify their phone number and connect their
**Telegram Wallet (TON)**, join events, and receive NFT badges that admins mint in bulk
from a list of phone numbers.

---

## 1. Vision & Core Flow

```
  USER                          ADMIN
   │  /start + share phone       │  create badge type (art, soulbound?)
   │  connect TON wallet         │  create event
   │  join event                 │  upload/paste phone numbers
   ▼                             ▼
       ┌─────────────────────────────────┐
       │  Backend maps phone → user →    │
       │  wallet → mints badge on TON    │
       └─────────────────────────────────┘
   │                                             │
   ▼                                             ▼
 badge in wallet / Mini App gallery      status per user (pending→minted/failed)
```

### User flow
1. User opens the bot → `/start` → taps **"Share phone number"** (`request_contact` keyboard button).
2. Bot creates/updates the user record (telegram_id + verified phone).
3. Bot sends a link to the **Telegram Mini App** where the user connects their
   **Telegram Wallet** via **TON Connect**.
4. Backend verifies the Mini App `initData` (HMAC with bot token) and stores the
   linked wallet address.
5. User joins an event from the bot (or by admin adding their phone number).
6. When minted, the badge appears in the user's wallet and in the Mini App gallery;
   the bot sends a notification.

### Admin flow
1. Admin logs into the **web dashboard**.
2. Creates a badge type: name, description, artwork, **transferable (TEP-62) or
   soulbound (TEP-85)** — decided per badge.
3. Deploys the corresponding collection contract to TON (testnet first).
4. Creates an event and assigns it a badge type.
5. Pastes or uploads a **list of phone numbers** (or picks from event attendees).
6. Hits "Mint batch" → backend maps each phone → linked wallet and mints one badge
   per user. Users who haven't linked a wallet yet get a reminder to connect.

---

## 2. Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                            TON blockchain                          │
│   BadgeCollection (TEP-62) / SoulboundBadgeCollection (TEP-85)     │
└──────────────▲───────────────────────────────▲─────────────────────┘
               │ mint / read (pytoniq + TonAPI)│
┌──────────────┴───────────────────────────────┴─────────────────────┐
│                        Python backend (FastAPI)                    │
│   • Mini App API  (wallet link, badge gallery, initData verify)    │
│   • Admin API     (badge/event CRUD, batch mint, status)           │
│   • Mint worker   (background queue, retries)                      │
│   • SQLite (SQLAlchemy)                                            │
└──────────────▲───────────────────────────────▲─────────────────────┘
               │                               │
   ┌───────────┴───────────┐       ┌───────────┴───────────┐
   │  Telegram bot         │       │  Frontends            │
   │  (aiogram 3.x)        │       │  • TON Mini App       │
   │  onboarding, events,  │       │  • Web admin dashboard│
   │  notifications        │       └───────────────────────┘
   └───────────────────────┘
```

### Components

| Component | Tech | Responsibility |
|---|---|---|
| Telegram bot | Python · aiogram 3.x | `/start`, phone request, event joining, mint notifications |
| Mini App API | FastAPI | TON Connect wallet linking, badge gallery, initData verification |
| Admin API | FastAPI | CRUD for badge types/events, batch mint triggers, status |
| Mint worker | asyncio task in backend | Consumes assignment queue, mints via pytoniq, retries on failure |
| DB | SQLite + SQLAlchemy | Users, wallets, badge types, events, assignments |
| Mini App frontend | Vite + React + `@tonconnect/ui-react` | Connect wallet, view badges |
| Admin frontend | Vite + React | Event/badge management, CSV upload, mint status table |
| Contracts | Tact | Badge NFT + Soulbound collections (Tact stdlib templates) |

### Key decisions
- **TON + Telegram Wallet** — native wallet inside Telegram via TON Connect v2.
- **Tact, not Solidity/FunC** — modern, safe, official standard-library templates for
  NFT (TEP-62) and SBT (TEP-85) collections.
- **One collection contract per badge type** — cleanest way to honour the
  *"admin decides per badge"* rule (soulbound is a contract-level property).
- **Phone number is the admin's key**; the linked wallet is the mint target.
  Phone → telegram_id → wallet_address chain stored in SQLite.
- **Admin hot wallet** (deployer/minter key) lives only in `.env` — never committed
  (already covered by `.gitignore`).
- **TonAPI (toncenter/Tonkeeper) key** for read calls (balances, metadata) — required
  at integration time.
- **SQLite** — chosen for the expected small scale; schema is portable to Postgres later.

---

## 3. Data Model

```sql
users        (id, telegram_id UNIQUE, username, phone, wallet_address,
              wallet_connected_at, created_at)
badge_types  (id, name, description, image_url, metadata_uri,
              is_soulbound BOOL, collection_address, supply, deployed_at, created_at)
events       (id, name, description, starts_at, badge_type_id FK)
attendees    (id, event_id FK, user_id FK, joined_at)          -- users who joined
assignments  (id, badge_type_id FK, user_id FK, status,
              tx_hash, error, created_at, minted_at)
             -- status: pending → queued → minting → minted | failed | needs_wallet
```

---

## 4. Proposed Repo Layout

```
UnityCommunityNftBot/
├── bot/                  # aiogram Telegram bot
│   ├── main.py
│   ├── handlers/         # start / onboarding / events / badges
│   └── keyboards.py
├── backend/              # FastAPI + worker
│   ├── main.py
│   ├── api/              # mini_app.py, admin.py
│   ├── db/               # SQLAlchemy models, session
│   ├── services/         # ton.py, wallet.py, mint.py
│   └── worker.py
├── contracts/            # Tact smart contracts
│   ├── transferable/     # TEP-62 collection (Tact)
│   ├── soulbound/        # TEP-85 collection (Tact)
│   ├── build/            # compiled artifacts (gitignored)
│   └── deploy/           # Python deploy scripts (testnet/mainnet)
├── web/
│   ├── miniapp/          # Vite + React + @tonconnect/ui
│   └── admin/            # Vite + React admin dashboard
├── tests/
├── .env.example          # bot token, admin key, TonAPI key, deployer mnemonic
├── .gitignore            # done
└── PLAN.md
```

---

## 5. Milestones

| Phase | Scope | Exit criteria |
|---|---|---|
| **0 · Foundations** | Repo scaffold, `.env.example`, git first commit | Bot & backend boot, DB migrations run |
| **1 · Contracts** | Tact badge collections (transferable + soulbound), deploy scripts, tests | Both contracts deploy on **testnet**, mint verified in explorer |
| **2 · Bot onboarding** | `/start`, `request_contact`, user record, wallet-link prompt | Phone captured; user record in SQLite |
| **3 · Mini App** | TON Connect, initData verification, badge gallery | User links wallet; address persisted; gallery shows owned badges |
| **4 · Admin + batch mint** | Badge/event CRUD, CSV upload, mint queue, Telegram notifications | Mint 10-test-number batch end-to-end on testnet |
| **5 · Hardening** | Retries, error alerts, admin auth, mainnet checklist, README | Runbook for going live |

---

## 6. Open Items (resolved at implementation time)
- TonAPI provider choice (toncenter vs Tonkeeper) — evaluate during Phase 4.
- Mini App hosting (static files served by FastAPI vs separate host).
- Admin authentication (single shared password vs per-admin accounts).
- Wallet connect via chat (aiogram-tonconnect) as an alternative to Mini App linking.
