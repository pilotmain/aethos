# Runbook: README + commit + push via host executor

This runbook describes **only** what exists in this repository: allowlisted `host_action` values, the **chat → approval → local tool worker** path, and Docker auth persistence. It does **not** include generic shell execution or a REST “execute host” API.

## Verify vs mutate (read this first)

| Step | What runs | Creates README / commit / push? |
|------|-----------|-----------------------------------|
| **Operator / CLI verification** (`try_operator_execution`, `gh auth status`, `vercel whoami`) | Read-only checks | **No** — proves login only |
| **Host executor** (`host_action`: `file_write`, `git_commit`, `git_push`, …) | Allowlisted tools after **approval** | **Yes** — one job per action (typically) |

Successful **verification does not queue** host-executor jobs. After a green `gh auth status`, you still ask separately for mutations (or enqueue payloads), then **approve** each host job when prompted.

Full architecture note: **`docs/HANDOFF_OPERATOR_EXECUTION_AND_ORCHESTRATION.md` §11.8**.

### FAQ: Why didn’t Nexa push after verifying GitHub / Vercel?

Because **verify** and **mutate** are **different subsystems**. The gateway may return after operator diagnostics (`handled=True`) without creating **`command_type: host-executor`** jobs. To push, use **`git_push`** (and usually **`file_write` + `git_commit`** first) as **separate** approved steps—see payload examples below.

### FAQ: What should I say for mutations?

Prefer **short, explicit** requests that match **`host_executor_intent`** patterns where possible (e.g. “git push”), or describe what you want so the UI/LLM builds **`payload_json`**. Long sentences mixing “check git AND add README AND push” are **not** automatically split into three host actions—use separate asks or queue payloads manually. **Optional:** enable **`host_action: chain`** so one approved job runs multiple allowlisted steps in order — see **`docs/WEEK2_HOST_ACTION_CHAINS.md`**.

## What does *not* exist (do not document or use)

| Claim | Reality |
|--------|--------|
| `host_action: "shell_exec"` | **Not implemented.** There is no arbitrary shell. |
| `POST /api/v1/host/execute` (or similar) | **Not in this app.** Host work runs as `command_type: "host-executor"` jobs after you confirm in **Telegram/Web UI**; a worker runs `host_executor.execute_payload`. |
| `$(date)` inside `file_write` `content` | **Not expanded** — you get the literal characters. Use a fixed date string. |

## What *does* exist

- **Host actions** (see `app/services/host_executor.py` and `app/services/host_executor_visibility.py`), including: `file_write`, `file_read`, `git_status`, `git_commit`, `git_push`, `list_directory`, `find_files`, `read_multiple_files`, and `run_command` with **fixed** `run_name` keys only (e.g. `pytest`, `git_status_short` — see `ALLOWED_RUN_COMMANDS` in `host_executor.py`).
- **Execution path**: natural language or UI → permission / confirmation → **queued job** → **local tool worker** → `execute_payload` / `execute_host_executor_job`.
- **GitHub / Vercel CLI auth in Docker**: persist `/root/.config/gh` and `/root/.vercel` via Compose named volumes (see `docker-compose.yml` and `docs/GUIDED_CLI_LOGIN_FOR_OPERATORS.md`).

## Prerequisites (one-time)

1. **`gh` authenticated** inside the API container: `docker exec -it nexa-api gh auth status`.
2. **Repository exists** on GitHub (404 → create with `gh repo create` or the UI).
3. **Repo cloned** under the **host executor work root** (`get_settings().host_executor_work_root`, often project root unless overridden). Example layout on macOS when repos live under your user directory:

   `<work_root>/pilot-command-center/.git/` (e.g. `/Users/you/pilot-command-center` on the host when `HOST_EXECUTOR_WORK_ROOT=/Users/you`)

   With Docker, use **`docker-compose.override.yml`** (copy from **`docker-compose.override.example.yml`**) to bind-mount your repos and set **`HOST_EXECUTOR_WORK_ROOT`** to the **container** path of that mount.

4. **Push credentials** for `git push` (HTTPS token / SSH) available **inside the environment where the worker runs**, same as manual `git push` from that host.

## Payload shapes (`payload_json` for host-executor jobs)

Paths are **relative to the work root**. There is **no** nested `"params"` wrapper — fields are top-level on the job payload.

### 1. Write README (static date)

```json
{
  "host_action": "file_write",
  "relative_path": "pilot-command-center/README.md",
  "content": "# Pilot Command Center\n\n## Service Status\n\nThis service has been stopped as requested on 2026-05-03.\n\nThe Vercel deployment has been removed.\n\nFor questions, contact the administrator.\n"
}
```

`cwd_relative` is **not** required for `file_write` if `relative_path` already includes the repo folder.

### 2. Commit (run git inside the repo)

```json
{
  "host_action": "git_commit",
  "commit_message": "docs: add service stop notification",
  "cwd_relative": "pilot-command-center"
}
```

### 3. Push

Default upstream:

```json
{
  "host_action": "git_push",
  "cwd_relative": "pilot-command-center"
}
```

Explicit remote and branch (optional):

```json
{
  "host_action": "git_push",
  "push_remote": "origin",
  "push_ref": "main",
  "cwd_relative": "pilot-command-center"
}
```

## Vercel (host executor)

These run the **Vercel CLI** with a **fixed argv** (no shell). You must be logged in (`vercel login` or `VERCEL_TOKEN` in the worker environment).

### List projects (read-only)

```json
{
  "host_action": "vercel_projects_list"
}
```

Natural language: *“list my Vercel projects”* / *“vercel projects list”* may infer this action (see `host_executor_intent`).

### Remove a project (destructive)

Requires an explicit boolean confirmation and a **slug** (not a URL path):

```json
{
  "host_action": "vercel_remove",
  "vercel_project_name": "pilot-command-center",
  "vercel_yes": true
}
```

`project_name` is accepted as an alias for `vercel_project_name`. **`vercel_yes` must be JSON `true`** so the implementation can run `vercel remove <slug> --yes` without a TTY. There is **no** free-text “stop service” → remove mapping in this repo; queue the structured payload (or use the LLM/UI to build it) and approve the job.

**Not implemented here:** chained workflows (remove → file_write → commit → push in one run), rate limits, and a generic `shell_exec` action. Run those steps as **separate** approved host-executor jobs in order.

## How to run it (correct testing path)

1. Open **Telegram** or **Web UI** and ask for the workflow in plain language, for example:  
   *“Add README.md under pilot-command-center with … then commit and push.”*
2. Approve **host-executor** jobs when prompted (and grant workspace permission if your deployment enforces it).
3. Do **not** use curl against a fictional execute endpoint; do **not** rely on `shell_exec`.

## Manual checks (optional)

```bash
docker exec -it nexa-api python -c "from app.core.config import get_settings; print(get_settings().host_executor_work_root)"
docker exec -it nexa-api sh -c 'ROOT=$(python -c "from app.core.config import get_settings; print(get_settings().host_executor_work_root)") && ls -la "$ROOT/pilot-command-center"'
docker exec -it nexa-api sh -c 'ROOT=$(python -c "from app.core.config import get_settings; print(get_settings().host_executor_work_root)") && cd "$ROOT/pilot-command-center" && git status && git remote -v'
```

## Related commits / docs

- `git_push` host action: commit `4c35bf0` on `main`.
- CLI auth volumes in Compose: commit `7ee90ea` and `docs/GUIDED_CLI_LOGIN_FOR_OPERATORS.md`.
- Operator vs host executor: `docs/HANDOFF_OPERATOR_EXECUTION_AND_ORCHESTRATION.md`.
