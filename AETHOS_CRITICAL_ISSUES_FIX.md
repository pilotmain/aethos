# AethOS critical issues — diagnosis and fixes

This document captures common setup mistakes and the fixes applied in-repo (or how to operate the system correctly). **Do not commit `.env`** — keep secrets local.

---

## 1. API won’t start — `Could not import module "main"`

**Cause:** Uvicorn was started with `uvicorn main:app`; this project’s ASGI app lives under **`app.main`**.

**Correct command (from repo root, venv active):**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Discover entry (optional):

```bash
rg "app = FastAPI\\(" app/main.py
```

---

## 2. HTTP 404 — wrong paths

There is **no** `POST /api/v1/chat`. Use versioned routes:

| Use case | Method | Path | Body notes |
|----------|--------|------|------------|
| Workspace web chat | POST | `/api/v1/web/chat` | JSON: `message` (required), `session_id` (optional) |
| Mission Control gateway (same engine as many tools) | POST | `/api/v1/mission-control/gateway/run` | JSON: **`text`** (or aliases `raw` / `message` / `prompt`), `user_id` |
| Agent roster | GET | `/api/v1/agents/list` | Headers: `X-User-Id`, optional `Authorization` |

**Web chat example:**

```bash
curl -sS -X POST "http://localhost:8000/api/v1/web/chat" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: tg_YOURID" \
  -H "Authorization: Bearer $NEXA_WEB_API_TOKEN" \
  -d '{"message":"Hello","session_id":"default"}'
```

**Gateway example:** the handler accepts **`text`**, **`raw`**, **`message`**, or **`prompt`** (first non-empty wins), via an explicit Pydantic body model — **not** a bare `dict` (avoids *Input should be a valid dictionary* when clients send only `raw`).

```bash
curl -sS -X POST "http://localhost:8000/api/v1/mission-control/gateway/run" \
  -H "Content-Type: application/json" \
  -d '{"text":"Create a marketing agent","user_id":"tg_YOURID"}'
```

See **`docs/API_AND_FRONTEND_CONNECTION.md`** for ports, auth, and `./scripts/fix_api_connection.sh`.

**Health:**

```bash
curl -sS "http://localhost:8000/api/v1/health"
```

If your UI prints URLs on another port (e.g. 8010), use the port where **you** actually run Uvicorn.

---

## 3. Agent recovery `403 Forbidden`

**Route:** `POST /api/v1/agent/health/{agent_id}/recover`

**Headers:** `X-User-Id` (required for web API), and **`Authorization: Bearer <NEXA_WEB_API_TOKEN>`** when the server is configured to require a bearer.

**Authorization logic (after fix):**

- Telegram-linked users: **owner** or **trusted** role; or
- **Orchestration owner:** `metadata.app_user_id` on the agent matches `X-User-Id`.

If you are only a **guest** in Telegram role and the agent is not stamped with your app user id, manual recover remains blocked (supervisor auto-recovery may still run).

---

## 4. Natural language agent creation returns `general_chat`

**Common causes:**

1. **Empty gateway body** — using only `"raw"` before the server accepted it; use `"text"` or upgrade to a build that accepts **`raw` / `message` / `prompt`** aliases on `/mission-control/gateway/run`.
2. **Parsing** — phrases like **“Create a marketing agent for product launch”** need the conversational parser to allow text **after** the word `agent`. That regex was tightened to allow an optional tail.

**Debug locally:**

```bash
python scripts/debug_nl_creation.py "Create a marketing agent for product launch"
```

---

## 5. `validate_aethos_env.py` / `ModuleNotFoundError: app`

Run from **repository root** with the project venv:

```bash
cd /path/to/aethos
.venv/bin/python scripts/validate_aethos_env.py
```

The script adds the repo root to `sys.path`. If you invoke modules as files from elsewhere, set:

```bash
export PYTHONPATH=/path/to/aethos
```

---

## 6. Operational checklist

1. Start API: `uvicorn app.main:app --reload --port 8000`
2. Health: `GET /api/v1/health`
3. Chat or gateway with correct JSON keys and auth headers
4. Recover: bearer + `X-User-Id` + ownership/trusted/orchestration-owner rule above

---

## Rollback

Revert individual commits touching:

- `app/services/sub_agent_natural_creation.py` (NL tail parsing)
- `app/api/routes/mission_control.py` (payload aliases)
- `app/api/routes/agent_health.py` (manual heal gate)

if a stricter owner-only policy is required in your deployment.
