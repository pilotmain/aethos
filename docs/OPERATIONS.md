# Operations (operator, stacks, and autonomy)

This document covers **always-on** and **automation** topics: the operator loop, host-side dev execution, and launchd supervision.

## Operator in Docker / API

The **API** runs an in-process scheduler. Every `OPERATOR_POLL_SECONDS` (default **20s**) it calls `process_supervisor_cycle` — that runs `scripts/dev_agent_executor.py` for approved work when `OPERATOR_AUTO_RUN_DEV_EXECUTOR` is `true` (as in many `.env.example` flows). **`.agent_tasks` is bind-mounted** from the repo (host `.agent_tasks` = `/app/.agent_tasks` in the container) so you can open `dev_job_*.md` in Cursor and the bot can read `dev_job_*.done.md` for handoff. `.runtime/` is typically a named volume.

The **image** does not include project `.git` unless you add a bind mount for a full local worktree. End-to-end verification: [DEV_JOB_FLOW.md](DEV_JOB_FLOW.md).

## Maximum autonomy and host executor

For **auto-approval** and hands-off dev runs, append `env.autonomy.example` to `.env` and review. That can enable auto-approval of queued dev work, auto review, and (optionally) auto commit. **Cursor** is not a headless service; the automated path is `DEV_AGENT_COMMAND` and/or the **Codex** CLI. In Docker, a **Linux** API container **cannot** run macOS **Codex.app** — for that model, set `OPERATOR_AUTO_RUN_DEV_EXECUTOR=false` where needed, set `DEV_EXECUTOR_ON_HOST=1`, and keep Postgres reachable from the host.

**Easiest path** after `./run_everything.sh start`: when `DEV_EXECUTOR_ON_HOST=1` is in `.env`, the script can also start a **host** dev executor in the **background** (log: **`.runtime/host_dev_executor.log`**; use **`RUN_EVERYTHING_NO_HOST_DEV=1`** to skip). You can run the executor in the foreground with **`./scripts/run_host_dev_executor.zsh`** or **`./scripts/host_dev_executor_loop.sh`**. If you see `reset: unknown terminal type API`, do not run the host helper via `bash …` in a bad TTY; use the documented paths or `run_everything`’s background start.

## Process supervision (no Docker, or in addition to compose)

```bash
./scripts/start_operator_stack.sh
./scripts/operator_stack_status.sh
./scripts/stop_operator_stack.sh
```

For macOS **launch on login** / keep-alive, install the LaunchAgent:

```bash
./scripts/install_launchd_operator.sh
```

The LaunchAgent runs a small supervisor loop that keeps the API and Telegram bot alive and restarts them if either process exits. It does **not** replace the in-app operator scheduler, but it helps after reboots.

**Health:** `GET /api/v1/health` — for API/bot PIDs when using the operator scripts, `scripts/operator_stack_status.sh`.

## Related

- [SETUP.md](SETUP.md) — Docker, `run_everything.sh`, bootstrap, LLM env.
- [DEV_JOBS.md](DEV_JOBS.md) — phone → machine → review loop and approvals.
- [DEV_JOB_FLOW.md](DEV_JOB_FLOW.md) — pipeline and verification.
- [MULTI_USER.md](MULTI_USER.md) — roles, BYOK, and `/access`.
