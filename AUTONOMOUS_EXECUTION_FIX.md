# Autonomous execution & budget dashboard alignment

## Budget tab showed 0 while chat showed real usage

**Cause:** `GET /api/v1/providers/usage` used the in-memory token-economy audit tail (`list_recent_token_audits` + `snapshot_for_user`). Workspace chat usage is persisted in **`llm_usage_events`** (same as `GET /api/v1/web/usage/summary`).

**Fix:** `app/api/routes/providers_usage.py` now builds **`build_llm_usage_summary("today", …)`** and **`get_recent_llm_usage`** from the DB, merges token/cost totals into the existing `summary` object (so `budgetInfoFromSummary` still works), and keeps Phase 38 fields like `budget_blocks_today` from `snapshot_for_user`. Extra response keys: `ok`, `llm_summary`.

## Host executor & workspace

**Cause:** Operators often skip executor env vars and workspace roots, so host jobs fail closed.

**Fix:**

- **`scripts/setup.py`** — new step **Host executor**: sets `NEXA_HOST_EXECUTOR_ENABLED`, `HOST_EXECUTOR_WORK_ROOT`, aligns `NEXA_WORKSPACE_ROOT`, optionally queues **`POST /api/v1/web/workspace/roots`** after health succeeds during verification (same session as Mission Control).
- **`scripts/show_credentials.sh`** — prints executor status from `.env`.
- **`app/services/agent_templates.py`** — predefined **developer** / **qa** presets for future UI or docs (not wired to spawn automatically).

## Env vars (reference)

- `NEXA_HOST_EXECUTOR_ENABLED` — must be true on the process that runs host execution.
- `HOST_EXECUTOR_WORK_ROOT` — default cwd / path base for host actions (see `.env.example`).

There is **no** separate `NEXA_HOST_EXECUTOR_ALLOWED_PATHS` in Settings; path policy uses workspace roots + permissions.

## Rollback

```bash
git checkout HEAD~1 -- app/api/routes/providers_usage.py scripts/setup.py
```

Adjust commit hash as needed.
