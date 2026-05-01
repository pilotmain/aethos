# Dev job flow (Telegram → executor → Cursor/Codex)

## What each step does

1. **You message the bot** — e.g. `Ask cursor to …` — the bot **creates** a row in the DB (`needs_approval` unless auto-approve is on).
2. **`approve job #N`** — status becomes **`approved`**. Nothing runs on disk until the next step.
3. **`dev_agent_executor.py` runs** — it must be started **regularly** (see modes below). It picks **`approved`** jobs, writes **`.agent_tasks/dev_job_N.md`**, sets status to **`waiting_for_cursor`**, and optionally runs **`DEV_AGENT_COMMAND`** / Codex. If no CLI is configured, you open the `.md` in Cursor and run the agent; when done, the marker **`.agent_tasks/dev_job_N.done.md`** drives the next steps (review / commit), handled on later executor runs.

## Two ways to run the executor (pick one)

| Mode | `.env` | Who runs `dev_agent_executor.py` |
|------|--------|-----------------------------------|
| **A. In Docker** | `OPERATOR_AUTO_RUN_DEV_EXECUTOR=true`, `DEV_EXECUTOR_ON_HOST=false` (or unset) | The **API** container, every `OPERATOR_POLL_SECONDS` (~20s), when work exists. Linux image: **no** macOS Codex.app; use bind-mounted **`.agent_tasks/`** with Cursor on the host. |
| **B. Host (macOS)** | `DEV_EXECUTOR_ON_HOST=1`, `OPERATOR_AUTO_RUN_DEV_EXECUTOR=false` | Your **Mac** via `./run_everything.sh start` (background) or `./scripts/run_host_dev_executor.zsh`. Uses **Postgres on `localhost:POSTGRES_HOST_PORT`** — same DB as Docker. |

If **`DEV_EXECUTOR_ON_HOST=1`**, the API container **does not** run the in-container executor (avoids two processes racing on the same job), even if `OPERATOR_AUTO_RUN_DEV_EXECUTOR` is still `true`.

## Check that it is working

1. **Stack up:** `./run_everything.sh start` (or your compose command).
2. **After** you approve a job, within ~20s (or one host loop tick):
   - **Mode A:** `docker compose logs api --tail 80` and look for executor output or `Prompt written to:`.
   - **Mode B:** `tail -f .runtime/host_dev_executor.log` — you should see `Prompt written to: .../dev_job_N.md` or Codex output.
3. **On disk:** `.agent_tasks/dev_job_N.md` should **exist** next to your repo.
4. **Dashboard:** `http://localhost:8000/dashboard` — job status should move past `approved` to `waiting_for_cursor` / `in_progress` / etc.
5. **API health details:** if exposed, `operator_settings.dev_executor_on_host` and `auto_run_dev_executor` show the active mode.

## If the job stays `approved`

- **Mode A:** `OPERATOR_AUTO_RUN_DEV_EXECUTOR` is `false` or the API container is not running.
- **Mode B:** Host executor is not running (`tail` the log file; restart `./run_everything.sh start` or the host script), or `DATABASE_URL` on the host cannot reach Postgres (check `POSTGRES_HOST_PORT` and that the `db` container is up).
