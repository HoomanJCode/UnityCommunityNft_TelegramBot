# UnityCommunity NFT Telegram Bot

> ## ⚠️ DISCLAIMER — DEMO / PRESENTATION ONLY
>
> **This repository exists solely for a simple presentation in a group.**
> It is **NOT intended for production** and **NOT for any real-world use**.
>
> - No security review has been performed.
> - Keys, secrets, and wallet flows are NOT hardened.
> - Nothing here should be deployed to mainnet or used with real funds, real
>   user data, or real phone numbers.
> - Treat everything in this repo as a throwaway demo of the concept.

---

## What it demonstrates

A concept for a Telegram-based NFT badge system:

- Users share their phone number with a Telegram bot
- Users connect a TON wallet (Telegram Wallet) through a Mini App
- Admins create events and NFT badges, then batch-assign badges to a list of
  phone numbers
- Badges are minted on TON as NFT / soulbound tokens

## Repository layout

```
bot/         Python Telegram bot (python-telegram-bot)
backend/     Flask backend + mint worker + SQLite
contracts/   TON smart contracts (Tact)
web/         Telegram Mini App + admin dashboard frontends
PLAN.md      Full project description and plan
TODO.md      Step-by-step task checklist with commit checkpoints
```

## Status

- ✅ Phase 0 · Foundations — repo scaffold, DB models, bot + backend boot
- ✅ Phase 2 · Bot Onboarding — /start, phone capture, user record, wallet prompt
- ⬜ Phase 1 · Contracts, Phase 3 · Mini App, Phase 4 · Admin + Mint, Phase 5 · Hardening

> **Note:** `aiogram`/`FastAPI` from the original plan were swapped for
> `python-telegram-bot`/`Flask` — the original stack requires Rust to build
> `pydantic-core`, which is unavailable in this environment.

## License

None. For presentation purposes only — do not reuse in production.
