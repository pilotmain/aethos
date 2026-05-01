# Development handoff — more work, faster onboarding

**Purpose:** Give a new developer, contractor, or AI agent a **short path** to run the app, know where the code lives, and **line up more development work** without re-reading the whole repo.

**Deeper product + architecture (north star, gaps, build order):** [CURSOR_HANDOFF.md](./CURSOR_HANDOFF.md) — read that for *what* to build next. **This** file is *how* to work in the repo day to day.

---

## 1. Get running (one place)

- **Stack (Docker + Telegram + API + optional host dev executor):** from the repo root  
  `./run_everything.sh start`  
  (refresh after code/`.env` changes: `./run_everything.sh stop` then `./run_everything.sh start`.)
- **Config:** copy `env.docker.example` → `.env` if needed; set at least `TELEGRAM_BOT_TOKEN` and (if you use real LLM) `USE_REAL_LLM=true` + keys. Postgres on host is usually `localhost:5433` (see `POSTGRES_HOST_PORT`).
- **End-to-end dev job flow (approve → executor → `.agent_tasks/`):** [DEV_JOB_FLOW.md](./DEV_JOB_FLOW.md).

---

## 2. Where the important code is

| What | Path |
|------|------|
| API entry, scheduler | `app/main.py` |
| Telegram bot, `/dev`, approvals | `app/bot/telegram_bot.py` |
| Operator (poll, dev executor trigger) | `app/workers/operator_supervisor.py` |
| Dev job runner, Cursor/Codex prompt files | `scripts/dev_agent_executor.py` |
| Host Mac executor entry | `scripts/host_dev_executor_loop.sh`, `host_dev_executor_bootstrap.py` |
| Stack runner | `run_everything.sh` |
| Handoff markers / Telegram nudges | `app/services/handoff_tracking_service.py` |

**Tests:** `pytest` from project root with the venv activated. Touch anything in `app/` and add/adjust `tests/` when you change behavior.

---

## 3. How “more work” gets into the codebase

1. **Product/roadmap ideas:** See **“Biggest current gaps”** and **“Concrete build order”** in [CURSOR_HANDOFF.md](./CURSOR_HANDOFF.md) — that is the intentional backlog.
2. **From Telegram (same path as “tell cursor to…”)** — queue a `dev_task` / dev executor job; it produces `dev_job_<id>.md` under **`.agent_tasks/`** and drives review/commit steps. Good for *specific* code tasks once the stack and DB are up.
3. **From the repo (you / another dev):** open a branch, use issues or a private tracker; keep [CURSOR_HANDOFF.md](./CURSOR_HANDOFF.md) in sync if you add major direction.
4. **Unattended automation (optional):** `DEV_AGENT_COMMAND` (e.g. Codex CLI on the Mac) + [README](../README.md) “Maximum autonomy” / `env.autonomy.example` if you want jobs to run without opening Cursor for every step.

---

## 4. Conventions (keep diffs small)

- Match existing patterns in the nearest file; no drive-by renames.
- **Safety:** new LLM-facing strings go through the patterns in [safe LLM usage](../app/services/safe_llm_gateway.py) unless clearly internal-only.
- **Secrets:** never commit `.env`; don’t log tokens.

---

## 5. Quick checklist before you say “we’re done”

- [ ] `pytest` passes (or you note what’s excluded and why).  
- [ ] If you changed API/bot: containers restarted (or at least `docker compose restart api bot` if you use compos e directly).  
- [ ] If you added user-facing behavior: update **README** or the relevant `docs/*.md` in the same PR.

---

**If you only read two docs:** this file + [CURSOR_HANDOFF.md](./CURSOR_HANDOFF.md). Product overview: [README.md](../README.md).
