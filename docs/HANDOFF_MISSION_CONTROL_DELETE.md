# Handoff: Mission Control delete / cleanup / stack UX changes

This summarizes repo changes around **Mission Control cleanup**, **browser reliability**, and **local stack defaults**. Use it to review, revert selectively, or continue work.

## Goal (original)

- Fix Mission Control **Delete**, **Reset**, **Delete everything**, and related actions when they appeared to do nothing.
- Improve PostgreSQL persistence for JSON flags (`flag_modified`).
- Optional nuclear DB purge for dev.

## Backend (`app/`)

| Area | Change |
|------|--------|
| `app/services/mission_control/cleanup_actions.py` | `flag_modified()` on `input_json` / `payload_json` after MC mutations (Postgres JSON reliability). |
| `app/services/mission_control/read_model.py` | Orchestration list excludes **`cancelled`** assignments (not only `hidden_from_mission_control`). |
| `app/api/routes/mission_control.py` | **POST aliases** for deletes (same behavior as DELETE): `/assignments/{id}/delete`, `/jobs/{id}/delete`, `/custom-agents/{handle}/delete`. **POST `/purge`**, **`GET /data-inventory`**, **`POST /database/purge-sql`** (gated by `NEXA_MISSION_CONTROL_SQL_PURGE`). Helpers `_mc_delete_*`. |
| `app/services/mission_control/db_purge.py` | Inventory + `purge_mission_control_database_for_user()` (hard SQL delete per user). |
| `app/core/config.py` | `nexa_mission_control_sql_purge`; default **`api_base_url`** set to **`http://localhost:8010`** (see port note below). |
| `app/main.py` | **CORS always on**; if `NEXA_WEB_ORIGINS` is empty, fallback origins `http://localhost:3000`, `http://127.0.0.1:3000`. |

## Frontend (`web/`)

| Area | Change |
|------|--------|
| `web/lib/api.ts` | Safe JSON/empty body handling; errors prefixed with HTTP status; **`fetchOrNetworkHint`** for clearer messages than raw “Failed to fetch”. |
| `web/lib/config.ts` | **`DEFAULT_API_BASE`** `http://127.0.0.1:8010`; optional **`NEXT_PUBLIC_NEXA_API_BASE`**; **migrate** saved `http://…:8000` → default API base on read. |
| `web/components/mission-control/MissionControlPage.tsx` | Success/error/refresh strip **under header**; delete actions use **POST** `…/delete` routes; purge/reset flows. |
| `web/components/nexa/WorkspaceApp.tsx` | Uses **`DEFAULT_API_BASE`** fallback. |

## Docker / scripts / docs

| File | Change |
|------|--------|
| `docker-compose.yml`, `docker-compose.sqlite.yml` | Host port **`8010:8000`**; **`API_BASE_URL=http://localhost:8010`** for api/bot. |
| `run_everything.sh` | Default health URL uses **8010**. |
| `scripts/check_nexa_stack.py` | Diagnostics; default API base **8010**. |
| `.env.example` | Comments for web/CORS, token, MC SQL purge, **8010** `API_BASE_URL`. |
| `README.md` | API link updated to **8010**. |

## Tests

- `tests/test_mission_control_cleanup_api.py` — includes POST delete alias test; uses `db_session.expire_all()` when asserting after API calls.
- `tests/test_mission_control_db_purge_api.py` — inventory + purge-sql gate.

## Environment variables (quick reference)

- **`NEXA_WEB_API_TOKEN`** — If set on API, browser login must send the same Bearer token or all authenticated calls fail with 401.
- **`NEXA_WEB_ORIGINS`** — Comma-separated; empty now falls back in code (see `main.py`).
- **`NEXA_MISSION_CONTROL_SQL_PURGE=true`** — Enables **`POST /api/v1/mission-control/database/purge-sql`** (destructive per-user SQL wipe).

## Why Mission Control “shows everything again”

Data is driven by **`GET /api/v1/mission-control/state`** (includes the former “summary” dashboard fields) against the **same database** the API uses. If the UI now reaches the API (correct base URL, CORS, server up), **assignments/jobs/trust lines reappear** — that is expected unless rows were removed or hidden. Deletes target rows **for the `X-User-Id`** in the request; mismatch → 404, no change.

## Reverting selectively

- **Port 8010**: revert `docker-compose*.yml` ports to `8000:8000`, restore **`DEFAULT_API_BASE`** / **`api_base_url`** / docs to **8000**, and **`run_everything.sh`** health URL.
- **CORS always-on**: revert `app/main.py` to only add middleware when `_cors` non-empty (not recommended — restores opaque browser failures).
- **POST delete routes**: keep or remove; frontend currently calls POST `…/delete`.
- **MC cleanup logic**: revert `cleanup_actions.py` / `read_model.py` only if you accept regressions on Postgres or cancelled rows still showing.

## Files to grep for full diff context

```bash
git log --oneline -- app/services/mission_control app/api/routes/mission_control.py web/lib web/components/mission-control web/components/nexa/WorkspaceApp.tsx app/main.py docker-compose.yml
```

---

*Prepared as a neutral handoff; adjust or revert any slice independently.*
