# Env completeness audit (Phase 4 Step 11)

**API:** `GET /api/v1/setup/env-audit`  
**Module:** `app/services/setup/env_completeness.py`

## Categories

| Category | Examples |
|----------|----------|
| Runtime | API URL, workspace, data dirs |
| Auth / MC | bearer token, user id, CORS, `web/.env.local` |
| Providers | routing mode, Ollama, LLM keys, fallback |
| Privacy | `NEXA_PRIVACY_MODE`, egress |
| Channels | Telegram, etc. (optional at setup) |
| Web search | Brave, Exa, … (optional) |
| Performance | truth cache TTL, slice TTL |

## Compatibility aliases

`NEXA_*` env names remain valid; setup writes both `AETHOS_*` and `NEXA_*` where applicable.

## Manual-only

Secrets such as `NEXA_SECRET_KEY` may require operator input outside the wizard.
