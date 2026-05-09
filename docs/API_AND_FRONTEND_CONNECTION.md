# API and frontend connection

## Ports

- **Next.js default API base** (`web/lib/config.ts`): **`http://127.0.0.1:8010`** (Docker / `nexa serve` convention maps host **8010** → app **8000**).
- If you run **`uvicorn app.main:app --port 8000`**, set **Mission Control → Connection → API base** to **`http://127.0.0.1:8000`** (same origin the browser must call).

`.env.example` **`API_BASE_URL`** should match wherever clients reach the API (bots, scripts).

## Authentication

| Endpoint | Headers |
|----------|---------|
| `POST /api/v1/web/chat` | **`X-User-Id`** + **`Authorization: Bearer <NEXA_WEB_API_TOKEN>`** when the server enforces the token |
| `POST /api/v1/mission-control/gateway/run` | Usually no bearer; **`user_id`** may be in JSON. Add bearer if your deployment requires it. |
| `POST /api/v1/agent/health/{id}/recover` | **`X-User-Id`** + optional bearer; must be **owner/trusted** or orchestration owner — see `app/api/routes/agent_health.py` |

## Gateway body (`/mission-control/gateway/run`)

Send a **JSON object** with at least one of:

- `text` (preferred)
- `raw`
- `message`
- `prompt`

First non-empty wins. Optional: `user_id`.

Example:

```bash
curl -sS -X POST "http://127.0.0.1:8010/api/v1/mission-control/gateway/run" \
  -H "Content-Type: application/json" \
  -d '{"text":"Create a marketing agent","user_id":"tg_YOUR_ID"}'
```

## CORS

`app/main.py` installs **`CORSMiddleware`** using **`NEXA_WEB_ORIGINS`** or defaults including **`http://localhost:3000`** and **`http://localhost:3120`**. If the browser shows “Failed to fetch”, add your dev origin to **`NEXA_WEB_ORIGINS`** (comma-separated).

## Helper script

```bash
./scripts/fix_api_connection.sh
```

Starts **`uvicorn`** on **8010** by default and probes health + gateway with a **`raw`-only** body.
