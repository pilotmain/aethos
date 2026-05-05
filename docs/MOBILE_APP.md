# Phase 30 — Mobile app (React Native)

The **`nexa-mobile/`** package is a React Native **TypeScript** client aligned with Phase 29 RBAC and Phase 27 Mission Control.

## Backend API (`/api/v1/mobile`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/mobile/auth/login` | Body `{ "user_id", "user_name?" }` → JWT + organizations |
| GET | `/mobile/me` | Bearer JWT → `{ user_id }` |
| GET | `/mobile/orgs` | List workspaces + active id |
| POST | `/mobile/orgs` | Create workspace |
| POST | `/mobile/orgs/{org_id}/active` | Set active workspace |
| GET | `/mobile/orgs/{org_id}/members` | Members |
| GET | `/mobile/orgs/{org_id}/projects` | Projects (`team_scope` = `mobile:{user_id}`) |
| POST | `/mobile/projects` | Create project |
| GET | `/mobile/projects/{id}/tree` | Mission tree JSON |
| POST | `/mobile/tasks` | Create task |
| GET | `/mobile/orgs/{org_id}/budget-summary` | Placeholder budget note |
| WS | `/mobile/ws/chat?token=` | Authenticated echo channel (extend to gateway) |

JWTs use **`NEXA_SECRET_KEY`** (see `app/core/mobile_token.py`). Tune lifetime with **`NEXA_MOBILE_TOKEN_TTL_HOURS`** (default 168).

## Mobile folder layout

See `nexa-mobile/README.md` for bootstrap (native `android/` / `ios/` via React Native CLI or Expo prebuild).

## CI

`.github/workflows/mobile.yml` runs **`npm install`** and **`npm run typecheck`** under `nexa-mobile/` when that tree changes.
