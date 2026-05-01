# Dev jobs (autonomous work from chat)

Nexa can run **codebase work** in a **review loop**: you queue a task (often from **Telegram** on your phone or from chat), a **dev executor** runs on a machine with the repo, and the bot **notifies** you for review, failure, and commit steps.

This does **not** need you to be on the same network as the machine, as long as **Telegram** works on your phone and an **always-on** host (laptop, mini PC, or server) is running: API, `python -m app.bot.telegram_bot`, the **operator** loop, and a **git** checkout of this repo (a zip with no `.git` is possible but with reduced branching/UX).

## What happens

1. You send a dev task: e.g. `Tell cursor to …` or `/improve …` — a **dev** job is **queued**. Optionally approve: `approve job #N` (or set `OPERATOR_AUTO_APPROVE_QUEUED_DEV_JOBS=true` on a trusted home box to skip the first approval).
2. The **dev executor** (`scripts/dev_agent_executor.py`) runs on that machine, creates a branch, and writes **`.agent_tasks/dev_job_N.md`**. The **Cursor** IDE does **not** receive Telegram; the bridge is the task file, plus (optionally) **`DEV_AGENT_COMMAND`** or the local **Codex** CLI for unattended runs.
3. The **bot** **polls** the DB; when a completion handoff file appears, the job moves to **ready for review** and you get a **Telegram** summary. You are also notified for **failed** and other terminal or review states.
4. You read the update, then: **`approve review job #N`** to continue, then **`approve commit job #N`** if your workflow needs it (see `/help` for current commands). For a **follow-up** change, queue a **new** job or extend the branch in your IDE and re-run the executor as documented in `dev_agent_executor.py`.

**“Remote from phone” vs local** is the same: only the **host** machine’s processes matter; Telegram is the only link the phone needs.

## Keep the machine “always listening” (API + bot + job runner)

1. **`.env`** in the project root: at least `TELEGRAM_BOT_TOKEN`, a database URL, and the keys the app should use.
2. **Start the stack** (or run in background), e.g. **`./scripts/start_operator_stack.sh`** (or Docker via [SETUP.md](SETUP.md)). The API’s lifespan in `app/main.py` also starts the scheduler for `process_supervisor_cycle` every `OPERATOR_POLL_SECONDS`.
3. Keep both **API** and **bot** up for a full *phone in → work out → message back* loop.
4. For **unattended** work (no human opening Cursor), set **`DEV_AGENT_COMMAND`** to a one-shot CLI that **reads the dev prompt on standard input** and edits the repo. It is not a file watcher, not a long IDE daemon, and it is not Cursor itself. The API scheduler runs `scripts/dev_agent_executor.py` when there is work; the script runs **`DEV_AGENT_COMMAND` once per job step** and waits for exit. If you set `DEV_AGENT` / tooling later, jobs that were *waiting for cursor* can be **picked up again** on the next run (or run `python scripts/dev_agent_executor.py` once in the project root with venv).
5. On macOS, install the LaunchAgent ([OPERATIONS.md](OPERATIONS.md)) to restart API/bot if they exit.

A **git** checkout is **recommended** (branches, commits, review diffs). A folder **without** `.git` is supported: the dev executor can skip branching and, after a successful run, move to review without creating commits. Remote vs local is unchanged: Telegram only talks to the bot, which uses the same DB as the host.

## Further reading

- [DEV_JOB_FLOW.md](DEV_JOB_FLOW.md) — end-to-end flow and verification.  
- [OPERATIONS.md](OPERATIONS.md) — operator, host dev executor, autonomy env.  
- [SETUP.md](SETUP.md) — `DEV_AGENT_COMMAND`, Codex fallback, Docker bind mounts.  
- Intent: user messages in the bot are classified; only **brain_dump** runs full plan generation for that path. See `app/services/intent_classifier.py`.

**Telegram commands (subset):** `/start`, `/help`, `/today`, `/overwhelmed`, `/prefs` — and dev-specific commands in `/help` and project docs for your deployment.
