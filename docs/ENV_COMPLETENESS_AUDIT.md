# Env completeness audit (Phase 4 Step 11, reaffirmed Step 17)

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

Step 17 setup covers: local/cloud routing, privacy/PII, egress, truth/slice cache TTLs, worker memory caps, runtime hydration flags, Mission Control bootstrap (`AETHOS_MC_*`), provider integrations, web search, channels, workspace paths. Verify with `GET /api/v1/setup/env-audit` after `aethos setup`.
