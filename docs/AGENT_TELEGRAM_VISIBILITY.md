# Telegram `/subagent list` vs Mission Control (Phase 64)

## Symptom

API / Mission Control show agents; Telegram `/subagent list` does not, often with “API list unavailable”.

## Cause

The bot loads the roster via **`GET {API_BASE_URL}{API_V1_PREFIX}/agents/list`** with **`X-User-Id: tg_<digits>`** (from your Telegram link). If that HTTP request fails (wrong `API_BASE_URL`, port, loopback DNS), the bot falls back to the **in-process SQLite registry**, which may not match the API process.

Scope mismatch **tg_** vs **telegram:** was addressed in Phase 61 for merged scopes; list calls use canonical **`tg_…`** via `validate_web_user_id`.

## Fix

1. Set **`API_BASE_URL`** to a URL you can `curl` from the host running the bot (try **`http://127.0.0.1:8010`** if `localhost` fails).
2. If **`NEXA_WEB_API_TOKEN`** is set, ensure the bot’s env includes the same token (the client sends `Authorization: Bearer` automatically).
3. Keep **one `DATABASE_URL`** for API and bot (Phase 60/62).
4. Restart API + bot after editing `.env`.

## Commands

- **`/agent_diagnostic`** — shows candidate API URLs, API success/failure, and local registry counts.
- **`/subagent list`** — uses API first (with localhost / 127.0.0.1 retry), then local registry.

See also: `.env.example` (`API_BASE_URL`).
