# Setup and local development

This is the long-form companion to the root [README.md](../README.md) — bootstrap, Docker, and API smoke tests.

## Quick start (recommended)

From the project root, one command (creates `.env` from the Docker template if it is missing, generates `NEXA_SECRET_KEY`, creates `.venv` when possible, and starts the Docker stack; then checks API health — set `TELEGRAM_BOT_TOKEN` in `.env` for the bot):

```bash
python scripts/nexa_bootstrap.py
```

Then open Telegram, send `/start`, and (for local LLM without the host’s system keys) add a key: `/key set openai` with your key from the provider, or set `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` in `.env` and `USE_REAL_LLM=true`.

- **Check-only (no start):** `python scripts/nexa_bootstrap.py --doctor` — the same class of static checks the API/bot print on startup, plus a quick health check if the API is up.
- **No Docker (generate `.env` + venv only):** `python scripts/nexa_bootstrap.py --no-docker`

Advanced options (tuning, ops, SQLite-only compose) are in the [Docker](#docker-postgres--api--telegram-bot) section below.

---

## One-line install

From an **empty directory**, this installs Nexa: clones the repo, runs the same Python bootstrap as [Quick start](#quick-start-recommended) (`nexa_bootstrap.py`), optionally merges API keys from your environment or prompts, runs `ensure_schema`, then starts services:

- **Default:** **Docker** (`./run_everything.sh start`) when the Docker daemon is available.
- **Otherwise:** **API + web on the host** (SQLite; Uvicorn + `npm run dev` for the Next.js app).

```bash
curl -fsSL https://pilotmain.com/install.sh | bash
```

The short URL above redirects to the installer script in this repo (`scripts/install.sh` on `main`). **Maintainers:** the redirect lives in the **pilotmain.com** site project (Vercel `vercel.json`), not in this repository; the canonical file URL is  
`https://raw.githubusercontent.com/pilotmain/nexa/main/scripts/install.sh`.

**Already cloned?** From the repository root:

```bash
./scripts/install.sh --no-clone
```

(or `./install.sh`.)

| Flag / env | Meaning |
| ---------- | ------- |
| `--no-docker` | Same as `nexa_bootstrap.py --no-docker`; install script tends to pick **host** start unless you override. |
| `--start docker` / `--start host` / `--start none` | Force startup mode (overrides auto-detection). |
| `NEXA_REPO_URL` | Git clone URL (default: `https://github.com/pilotmain/nexa.git`). |
| `NEXA_DIR` | Clone directory name (default: `nexa`). |
| `NEXA_START` | Same as `--start`: `none`, `docker`, or `host`. |
| `NEXA_NONINTERACTIVE=1` | No prompts (set keys via env). |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN` | Written into `.env` when set in the environment. |
| `PORT` | API port for **host** mode (default `8000`). |

After install, the API is typically at `http://localhost:8000` and the web UI at `http://localhost:3000` when the web process started successfully.

## Local development (no Docker, optional)

For SQLite + API on the host only, you can use `run.sh` after `cp .env.example .env` and filling values. For the standard Postgres + API + bot experience, use the quick start above.

## Optional real LLM mode

Set:

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL` (optional; default is a current Haiku 4.5–class snapshot; older `claude-3-5-haiku-20241022` is **retired** on the API)
- `USE_REAL_LLM=true`

If not set, the app uses a deterministic local fallback extractor and planner so you can test instantly.

For autonomous dev-job execution, set `DEV_AGENT_COMMAND` to your own agent (stdin = prompt) when you can. If it is blank and you did not set `DEV_AGENT_DISABLE_CODEX_FALLBACK`, the dev executor can fall back to the local **Codex** app CLI (default path overridable with `DEV_AGENT_CODEX_PATH`).

**Phone-only dev jobs (no `approve job #N`):** on a trusted always-on machine, set `OPERATOR_AUTO_APPROVE_QUEUED_DEV_JOBS=true` in `.env` and keep the operator stack running. Default is `false` for safety. See [DEV_JOBS.md](DEV_JOBS.md) and [OPERATIONS.md](OPERATIONS.md).

## Docker (Postgres + API + Telegram bot)

Requires [Docker](https://docs.docker.com/get-docker/) with **Compose v2.22+** recommended (for [Compose Watch](https://docs.docker.com/compose/file-watch/)).

### `run_everything.sh` (recommended)

**Background (always on, no re-run to “keep listening”):** start the stack in the **background** once, leave Docker / Docker Desktop running, and the **Telegram bot** will keep long-polling and the **API** will keep running the **operator** on `OPERATOR_POLL_SECONDS` (default: every 20s) so dev jobs and tools can be picked up without re-running a script.

```bash
cd /path/to/nexa
chmod +x run_everything.sh
./run_everything.sh start
```

(Equivalent: `./run_everything.sh --detach` or `-d`.) Containers use `restart: unless-stopped` so they come back if they crash. To change code, rebuild/restart, or for local dev with hot-reload, use the foreground command below or see `docs/CURSOR_HANDOFF.md` and Compose Watch.

**Foreground + file watch (while editing code):**

```bash
./run_everything.sh
```

**Troubleshooting** `command not found` or `sudo: ... command not found`:** you must be in the project root, the script must be executable (`chmod +x run_everything.sh`), and you should **not** use `sudo` with this script. On macOS with Docker Desktop, `docker` does not need root.

- Creates **`.env`** from `env.docker.example` if missing; edit `TELEGRAM_BOT_TOKEN` and LLM keys.
- Brings up **Postgres + API + bot** and, when supported, runs `docker compose watch`: changes under `app/` and `scripts/` are synced and containers restarted; changes to `requirements.txt` or `Dockerfile` trigger a **rebuild**.
- `USE_SQLITE=1 ./run_everything.sh start` — SQLite stack, always on.
- `./run_everything.sh stop`, `status`, `logs` — control the same compose project.

**Manual compose** (equivalent without the script):

1. `cp env.docker.example .env` and set secrets.
2. `docker compose up --build`
3. API: `http://localhost:8000` — OpenAPI: `/docs`

**PostgreSQL 16** is service `db` (default user / password / DB: `overwhelm` / `overwhelm` / `overwhelm`). The database is published on the host as **port 5433** by default (see `POSTGRES_HOST_PORT` in `.env`) to avoid clashing with local Postgres on 5432; inside Docker the `api` and `bot` services use `db:5432` via the compose `DATABASE_URL`.

**SQLite in Docker (no Postgres):** `docker compose -f docker-compose.sqlite.yml up --build` (or `USE_SQLITE=1 ./run_everything.sh`).

**Host dev executor:** when `DEV_EXECUTOR_ON_HOST=1` is in `.env`, the stack can start a **host** dev executor in the background (log: `.runtime/host_dev_executor.log`). Use `RUN_EVERYTHING_NO_HOST_DEV=1` to skip. For hands-off operation with **Codex** on macOS from Linux API containers, see [OPERATIONS.md](OPERATIONS.md#maximum-autonomy-and-host-executor). More detail: [DEV_JOB_FLOW.md](DEV_JOB_FLOW.md).

**Workspace strict mode and host permission grants** (`NEXA_WORKSPACE_STRICT`, Docker work roots, approve-after-grant behavior): [WORKSPACE_AND_PERMISSIONS.md](WORKSPACE_AND_PERMISSIONS.md).

**Stop:** `docker compose down` or `./run_everything.sh stop` (add `-v` to remove volumes and Postgres data).

**API + Telegram on the host (no full compose):** from the project root, `./run_dev_stack.sh` (kills old processes, starts Uvicorn and the bot; requires a configured `.env`).

**Telegram bot in dev** (if not using compose): with `TELEGRAM_BOT_TOKEN` in `.env`:

```bash
source .venv/bin/activate
python -m app.bot.telegram_bot
```

Open docs: `http://localhost:8000/docs`  
Operator dashboard: `http://localhost:8000/dashboard`

## After finishing work (mandatory for contributors and agents)

**Hard rule:** when you change code, always end with verification and process restarts (do not hand off without these).

1. **Tests (rerun)**  
   - `python -m compileall -q app` (must exit 0).  
   - Short intent / behavior smoke (with `USE_REAL_LLM=false` in `.env` unless you are explicitly testing the LLM path).

2. **Both processes (restart)** if you use the two-process layout: stop the project’s **Uvicorn** and **Telegram bot**, then from the project root (venv active):  
   - API: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`  
   - Bot: `python -m app.bot.telegram_bot`  
   Confirm Uvicorn is up on 8000 and the bot log shows Telegram `getMe` (or equivalent) 200.

Persistent guidance for this workflow lives in `.cursor/rules/finish-work-verification.mdc`.

## Suggested test flow

1. Start the API.
2. Send a brain dump to `/api/v1/plans/generate` or to the Telegram bot.
3. Check `/api/v1/tasks` and `/api/v1/plans/today`.
4. Use `/today` in Telegram or `GET /api/v1/checkins/pending`.
5. Mark tasks done or snooze them.

## Main API endpoints (summary)

- `GET /api/v1/health`
- `GET /api/v1/auth/me`
- `POST /api/v1/dumps`
- `POST /api/v1/plans/generate`
- `GET /api/v1/plans/today`
- `POST /api/v1/plans/morning-refresh`
- `GET /api/v1/tasks` … `POST /api/v1/tasks` … `POST /api/v1/tasks/{id}/complete` / `snooze`
- `GET /api/v1/checkins/pending` … `POST /api/v1/checkins/respond`
- `GET /api/v1/web/memory` — `PUT /api/v1/web/memory/preferences` (agent memory; legacy `/api/v1/memory` returns 410)
- `GET /api/v1/jobs` … and job decision / review-approve / commit-approve
- `POST /api/v1/internal/process-due-checkins` — `process-job-handoffs` — `process-supervisor-cycle`

**Notes:** API auth uses `X-User-Id` for the API; Telegram users map to app users. Follow-ups are generated and stored; the bot and internal routes process due prompts. See [OPERATIONS.md](OPERATIONS.md) for operator scheduling.

## Project structure

```text
app/
  api/routes/
  core/
  models/
  repositories/
  schemas/
  services/
  workers/
  bot/
```

## Notes

- A malformed `.env` line (e.g. a product name with spaces) is loaded safely via `emit_sh_exports_from_dotenv.py` for shell helpers, not with raw `source` where that would break.
- A `PTBUserWarning` about `create_task` in `post_init` on the bot may appear; it does not block startup.

For architecture, roadmap, and handoff, see [CURSOR_HANDOFF.md](CURSOR_HANDOFF.md). For the dev job pipeline, see [DEV_JOB_FLOW.md](DEV_JOB_FLOW.md) and [DEV_JOBS.md](DEV_JOBS.md).
