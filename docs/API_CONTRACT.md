# Nexa-Next API contract (frozen)

**Rule:** Do not add or rename public HTTP routes without updating this file and adding/adjusting contract tests.

Base URL prefix: **`/api/v1`** (unless noted).

---

## Mission Control

| Method | Path | Notes |
|--------|------|--------|
| GET | `/mission-control/state` | Unified dashboard + execution snapshot (`hours` query 1–168). Requires `X-User-Id`. |
| GET | `/mission-control/graph` | Derived graph; same auth/window as `/state`. |
| GET | `/mission-control/events/timeline` | Event history. |
| WebSocket | `/mission-control/events/ws` | Live JSON stream. |
| GET | `/mission-control/summary` | **Removed** — returns HTTP **410 Gone** (use `/state`). |

---

## Dev runtime

| Method | Path |
|--------|------|
| POST | `/dev/workspaces` |
| GET | `/dev/workspaces` |
| GET | `/dev/workspaces/{workspace_id}` |
| POST | `/dev/runs` |
| GET | `/dev/runs` |
| GET | `/dev/runs/{run_id}` |
| POST | `/dev/runs/{run_id}/retry` |

---

## Memory

| Area | Path pattern |
|------|----------------|
| Agent memory (preferences, soul, notes, forget) | `/web/memory`, `/web/memory/state`, `/web/memory/*` |
| Persistent Nexa memory documents | `/nexa-memory` (GET/POST `""`) |
| Legacy | `/memory/*` — **410 Gone** — do not use |

---

## Agents

| Method | Path |
|--------|------|
| GET | `/custom-agents` |
| GET | `/custom-agents/{handle}` |
| POST | `/custom-agents` |
| PATCH | `/custom-agents/{handle}` |
| DELETE | `/custom-agents/{handle}` |

There is **no** `/agents` alias.

---

## System

| Method | Path | Notes |
|--------|------|--------|
| GET | `/system/health` | Production readiness probe (DB, scheduler hint, privacy mode, runtime). |
| GET | `/system/metrics` | In-process counters. |

---

## Error envelope (JSON)

For most HTTP errors the API returns:

```json
{
  "ok": false,
  "error": "human-readable message",
  "code": "ERROR_CODE"
}
```

Validation (422) uses `code: "VALIDATION_ERROR"`. See `app/main.py` exception handlers.
