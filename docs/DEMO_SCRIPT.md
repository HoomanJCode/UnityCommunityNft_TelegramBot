# Demo Script & Presentation Talking Points

A ~10 minute walkthrough of the whole product. Screenshots of each stage are
listed inline so the deck can be assembled before the live demo.

---

## Act 1 — The problem & the flow (1–2 min)

**Talking points:**
- Community NFT badges handed out at events — but minting NFTs per attendee is
  tedious and technical.
- Our bot turns a phone list into on-chain badges with zero user friction.

**Slide:** the user/admin flow diagram from the README (Mermaid → screenshot).

---

## Act 2 — Bot onboarding (2 min, live)

**Steps:**
1. Open Telegram → `/start` with the bot.
2. Tap **Share phone number**.
3. Bot confirms: user stored, prompts to connect a TON wallet.

**Screenshots:** `/start` message, phone-share keyboard, confirmation.

**Talking point:** phone → user → wallet chain is the backbone — admins later
mint purely from phone numbers.

---

## Act 3 — Admin dashboard (3 min, live)

**Steps:**
1. Open `web/admin` → sign in with the admin password (shows the auth gate).
2. Create a badge type: name, description, **transferable vs soulbound**.
3. Create an event and attach the badge.
4. **Batch mint:** paste 3 phone numbers → submit → assignments appear with
   `pending` status.
5. Click **Verify on-chain** on a deployed collection to show the TonAPI
   integration (live network data).

**Screenshot:** dashboard tabs, badge cards, batch-mint result summary.

---

## Act 4 — The mint pipeline (2 min, live)

**Steps:**
1. Watch the worker drain the queue (`python -m backend.services.ton`).
2. Statuses flow `pending → queued → minting → minted`.
3. Each user gets a 🎉 Telegram notification with the tx hash.

**Talking point:** retries (up to `MAX_RETRIES`), atomic claiming (no double
mints), and the 🚨 admin alert if a mint fails permanently.

---

## Act 5 — User side (2 min, live)

**Steps:**
1. User opens the Mini App from the bot → TON Connect → wallet linked.
2. Badge gallery shows the minted badge.

**Screenshots:** Mini App home, TON Connect modal, gallery with badge.

---

## Act 6 — Contracts (1 min, screenshots)

- Transferable collection (TEP-62) + soulbound collection (TEP-85) written in
  **Tact**, compiled, and covered by 10 sandbox tests.
- Show `contracts/build/` + the test output (`npx jest`).

**Talking point:** the custom `Mint` body mints **directly to the user's
wallet** in one transaction (documented in the README's Contract ↔ client
compatibility section).

---

## Common questions

| Question | Answer |
|---|---|
| Why SQLite? | Demo-scope storage; SQLAlchemy keeps a Postgres swap trivial. |
| Why per-badge collections? | Soulbound is a contract-level property, so each badge type gets its own collection. |
| Is admin auth real? | Shared password → short-lived bearer tokens; mainnet checklist covers hardening. |
| What's next? | TonAPI read calls are in; live testnet E2E + mainnet deploy remain. |
