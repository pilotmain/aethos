# AethOS HTTP API (overview)

The **contract** for public, versioned paths (change policy for contributors) is **[API_CONTRACT.md](API_CONTRACT.md)**. Read that file before adding or renaming routes.

## Common entrypoints

| Area | Base (typical) | Notes |
|------|----------------|--------|
| Web UI backend | `/api/v1/web/...` | Sessions, chat, workspace projects, keys — see [WEB_UI.md](WEB_UI.md) |
| Mobile | `/api/v1/mobile/...` | JWT `Authorization: Bearer` — [MOBILE_APP.md](MOBILE_APP.md) |
| Agent orchestration | `/api/v1/agents/...` | Sub-agent registry CRUD, execute — [AGENT_ORCHESTRATION.md](AGENT_ORCHESTRATION.md) |
| Health | `/api/v1/health` | Liveness for load balancers |

`X-User-Id` for web-style auth uses validated channel ids (`tg_<digits>`, `web_*`, etc.); see `app/services/web_user_id.py`.

## Workspace projects (web)

- `GET/POST/DELETE /api/v1/web/workspace/nexa-projects` — register labeled folders under the host work root (after [WORKSPACE_AND_PERMISSIONS.md](WORKSPACE_AND_PERMISSIONS.md)).

Non-Telegram web user ids may manage their own projects; Telegram-linked users need **owner** or **trusted** role (see Phase 42).
