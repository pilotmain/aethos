# Cron scheduling & proactive automation (Phase 13)

**Status:** Implemented — AsyncIOScheduler + SQLite job metadata + REST API (`/api/v1/cron/*`).

## Components

| Piece | Role |
| ----- | ---- |
| `app/services/cron/models.py` | `CronJob`, `JobActionType`, `JobStatus` |
| `app/services/cron/job_store.py` | SQLite persistence (`nexa_cron_job_store`) |
| `app/services/cron/executor.py` | Runs skills, host payloads, Telegram/Slack messages, webhooks |
| `app/services/cron/scheduler.py` | `NexaCronScheduler` singleton (memory job store + reload from SQLite on API boot) |
| `app/api/routes/cron_automation.py` | Bearer-authenticated CRUD |
| `app/channels/commands/cron_http.py` | Telegram/Slack/CLI HTTP client |
| `nexa_cli cron …` | CLI wrapper |

## Configuration

| Env | Purpose |
| --- | ------- |
| `NEXA_CRON_ENABLED` | Master switch (default true). |
| `NEXA_CRON_DEFAULT_TIMEZONE` | Default IANA zone (e.g. `UTC`, `America/New_York`). |
| `NEXA_CRON_JOB_STORE` | SQLite URL for job rows (default `<repo>/data/nexa_cron_jobs.sqlite`). |
| `NEXA_CRON_API_TOKEN` | **Required** for Telegram `/schedule`, Slack `/nexa_cron`, and `nexa cron` CLI — must match between processes. |

Execution runs **inside the API process** when `NEXA_CRON_ENABLED=true`. Chat commands call the HTTP API so the Telegram bot process does not duplicate schedulers.

## Action types

- `channel_message` — `action_payload`: `{channel: telegram|slack, chat_id|channel_id, message}`
- `skill` — `{skill_name, input: {...}}`
- `host_action` — `{payload: {...}}` or raw host_executor dict
- `chain` — `{actions: [payload, ...]}`
- `webhook` — `{url, method?, json?, headers?}`

## Interfaces

- **Telegram:** `/schedule`, `/cron_list`, `/cron_remove` (see `telegram_adapter`).
- **Slack:** `/nexa_cron list|remove|schedule …` (register slash command in Slack app).
- **CLI:** `python -m nexa_cli cron list|add|remove|pause|resume`.

## Related

Existing mission scheduler API remains at `/api/v1/scheduler/*` (Phase 22). Phase 13 cron is separate automation with richer action types.
