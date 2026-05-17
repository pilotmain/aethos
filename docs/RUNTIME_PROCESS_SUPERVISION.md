# Runtime process supervision (Phase 4 Step 18)

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
