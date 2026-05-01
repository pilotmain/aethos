# Mission Control delete / reset — checklist vs Nexa codebase

Maps the external runbook (user-id consistency, hard delete, purge, read model, fetch errors, `reset-hard`) to what exists in this repo and what was intentionally **not** implemented.

## User identity

| Runbook | Nexa |
|--------|------|
| Default `X-User-Id: dev_user` everywhere | **Rejected.** Would merge distinct users. Login page + `webFetch` send the configured user id; backend resolves `get_valid_web_user_id`. Mismatched id → **404** on scoped deletes (expected). |
| Resolve user id in deps | Use **`get_valid_web_user_id`** (and related helpers), not a silent `dev_user` fallback. |

## Hard delete vs soft hide

| Runbook | Nexa |
|--------|------|
| `NEXA_DEV_ALLOW_HARD_DELETE` | **`app/core/config.py`** — gates query-param hard delete on assignment/job **DELETE** and **POST …/delete** routes when implemented there. |
| Soft delete only | Cleanup paths may set **`hidden_from_mission_control`** / **`cancelled`** when hard delete is off; SQL purge bypasses that for a full wipe. |

## Delete coverage (tables + files)

| Runbook | Nexa |
|--------|------|
| Generic table names (`HostJob`, etc.) | Nexa models use **`AgentJob`**, **`AgentAssignment`**, org/role tables, **`UserAgent`**, **`AccessPermission`**, optional **`AuditLog`**. See **`app/services/mission_control/db_purge.py`** — **`purge_mission_control_database_for_user`**. |
| `shutil.rmtree` of `/workspace/...` | **Not** raw tree deletes. Workspace clears go through **`clear_workspace_reports`** (and related) inside purge / reset flows, respecting **`NEXA_REPORTS_DIR`** / **`NEXA_MEMORY_DIR`**. |

## Read model

| Runbook | Nexa |
|--------|------|
| Exclude cancelled / deleted / hidden | **`app/services/mission_control/read_model.py`** + orchestration filters align with **`cleanup_actions`** (cancelled assignments, hidden rows). |

## Frontend fetch errors

| Runbook | Nexa |
|--------|------|
| Throw on non-OK with body text | **`web/lib/api.ts`** — non-OK responses surface status + body; network failures get **`fetchOrNetworkHint`**. |

## API base / port

| Runbook | Nexa |
|--------|------|
| Single port (8010) | **`web/lib/config.ts`** default base **`http://127.0.0.1:8010`**; migrates stored **8000** → default. Docker maps **8010→8000**; env docs in **`.env.example`** / **`README`**. |

## SQL purge + `reset-hard`

| Runbook | Nexa |
|--------|------|
| `POST …/database/purge-sql` | Implemented; requires **`NEXA_MISSION_CONTROL_SQL_PURGE=true`**. |
| `POST …/reset-hard` | **Alias** — same handler body as purge-sql; see **`app/api/routes/mission_control.py`** (`_mc_sql_purge_or_403`). Mission Control UI: **Hard erase (SQL)** button → **`/mission-control/reset-hard`**. |

## Logging

| Runbook | Nexa |
|--------|------|
| Debug prints | Prefer **`logging`** — e.g. start/end of **`purge_mission_control_database_for_user`** in **`db_purge.py`**, cleanup actions in **`cleanup_actions.py`**. |

## Verification SQL (local)

After a successful SQL purge for user `your_web_user_id`:

```sql
SELECT COUNT(*) FROM agent_assignments WHERE user_id = 'your_web_user_id';
SELECT COUNT(*) FROM agent_jobs WHERE user_id = 'your_web_user_id';
```

Expect **0** when purge ran with defaults clearing those rows.

---

See also **`docs/HANDOFF_MISSION_CONTROL_DELETE.md`** for stack and operational notes.
