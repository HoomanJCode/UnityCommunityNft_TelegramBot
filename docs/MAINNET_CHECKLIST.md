# Mainnet Deployment Checklist

Everything that must happen — and be verified — before going live on TON
mainnet. Work through it top to bottom; every item is a hard gate.

## 0. Pre-flight (security review)

- [ ] **Rotate all credentials**: generate a fresh 24-word `DEPLOYER_MNEMONIC`
      (never reuse a testnet or dev mnemonic). Store it in a password manager,
      not in the repo or `.env`.
- [ ] Create a dedicated **TonAPI key** for production (paid tier if the free
      1-req/4s limit is too tight for batch mints).
- [ ] Set a strong `ADMIN_PASSWORD` (≥ 16 chars, not `change_me`) — auth is
      *disabled* until it's set.
- [ ] Set `ADMIN_CHAT_ID` so the operator receives 🚨 mint-failure alerts.
- [ ] Verify `.env` is gitignored and no secrets ever landed in git history
      (`git log -p -- .env` should be empty).
- [ ] Put the production SQLite file (or Postgres) on a volume that is
      **backed up** — the DB holds the assignment state machine.
- [ ] Review `backend/api/admin.py` — if the dashboard is exposed publicly,
      consider IP allow-listing in front of it as defense-in-depth.

## 1. Contracts

- [ ] Deploy **transferable** collection to mainnet:
      `python contracts/deploy/deploy_collection.py transferable`
      (set `TON_NETWORK=mainnet`).
- [ ] Deploy **soulbound** collection to mainnet.
- [ ] Fund both collection deploy transactions from the production wallet
      (mainnet TON, not testnet faucet).
- [ ] Verify both deployments in a mainnet explorer and via
      `GET /admin/tonapi/collections/<address>` (needs mainnet TonAPI key).
- [ ] Set each badge type's `collection_address` via the admin API/dashboard.

## 2. Backend & env

- [ ] `TON_NETWORK=mainnet` everywhere (backend + worker).
- [ ] `MINI_APP_URL` / `ADMIN_WEB_URL` point at the **production** frontend
      origins; update the CORS allow-list in `backend/main.py` accordingly.
- [ ] `MINI_APP_BOT_TOKEN` matches the production bot token (initData HMAC
      will fail otherwise).
- [ ] Switch `DATABASE_URL` to managed Postgres if you outgrow SQLite
      (SQLAlchemy is already database-agnostic; run Alembic migrations).
- [ ] Run `python -m pytest tests/` green against the production branch.
- [ ] Serve the Flask app behind a real WSGI server (gunicorn/waitress), not
      `app.run(debug=True)`.

## 3. Frontends

- [ ] Build and deploy `web/miniapp` (Vite build → static host / Telegram
      serves it via the bot's Mini App settings).
- [ ] Build and deploy `web/admin` with `VITE_API_BASE` pointing at the
      production API.
- [ ] Re-point the Telegram bot's Mini App URL in @BotFather to production.
- [ ] Smoke-test the login flow, badge gallery, and batch mint against
      production from a clean browser.

## 4. Live smoke test (small, then big)

- [ ] Mint 1 badge to a personal test wallet on **mainnet**.
- [ ] Verify the NFT appears in the wallet + explorer + Mini App gallery.
- [ ] Force a failure (e.g. mint to a burned address) and confirm the admin
      🚨 alert fires and the user gets the ❌ message.
- [ ] Then run a 10-phone batch mint and watch it drain to `minted`.

## 5. Go-live

- [ ] Final `git tag v1.0.0` + push.
- [ ] Announce the bot publicly.
- [ ] Watch the first hour of logs for `mint failed` / worker loop errors.
