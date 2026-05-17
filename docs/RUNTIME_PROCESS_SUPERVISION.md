# Runtime process supervision (Phase 4 Step 18–19)

Coordinates API ownership, Telegram polling, SQLite startup, and hydration serialization.

## APIs

- `GET /api/v1/runtime/ownership`
- `GET /api/v1/runtime/services`
- `GET /api/v1/runtime/processes`
- `GET /api/v1/runtime/db-health`
- `GET /api/v1/runtime/startup-lock`

## CLI

- `aethos runtime ownership`
- `aethos runtime services`
- `aethos runtime takeover`
- `aethos runtime release`
- `aethos restart runtime`

Locks: `~/.aethos/runtime/ownership.lock`, `startup.lock`, `process_lifecycle.json`.

## Step 19 additions

- `GET /api/v1/runtime/supervision`
- `scripts/verify_runtime_supervision.sh`
- Mission Control `/mission-control/runtime-supervision`
- SQLite lock recovery fields and calm startup
- Telegram ownership UX and embedded `aethos restart bot`
- Uvicorn reload parent filtering

See also: `RUNTIME_OWNERSHIP_MODEL.md`, `SQLITE_OPERATIONAL_STABILITY.md`, `TELEGRAM_RUNTIME_OWNERSHIP.md`, `UVICORN_RELOAD_MODE.md`, `RUNTIME_SUPERVISION_VERIFICATION.md`, `RUNTIME_RECOVERY_ACTIONS.md`.
