# Phase 73d — Self-Improvement: CI Polling, Auto-Merge, Graceful Restart

> **TL;DR.** Phase 73d closes the Genesis Loop. It adds remote-CI awareness
> (via combined commit-statuses + Actions check-runs), an in-process
> background monitor that polls every open self-improvement PR, an opt-in
> per-proposal "auto-merge on CI pass" flag, and a graceful API-restart
> mechanism with five different methods (the dev-friendly default touches
> a sentinel module so a `uvicorn --reload` worker reloads in-process).
> A minimal `.github/workflows/python-ci.yml` is shipped so the polling
> has something real to wait on.

---

## 1. Spec audit and what we landed differently

The user-supplied spec (`Phase 73d: Graceful Restart & Remote CI Integration`)
called for `get_pr_combined_status` (legacy commit-statuses only), an
unbounded `while True` poll-task per PR, and a `sys.exit(0)` restart endpoint
with a `systemd | docker | supervisor | custom` switch. Five things needed
adapting before we could safely ship them on this codebase:

| Spec | What we did instead | Why |
|---|---|---|
| `get_pr_combined_status` (legacy commit-statuses only) | `get_pr_ci_status` AND-s **legacy commit-statuses ∪ Actions check-runs** | GitHub Actions reports via the modern check-runs API. Ignoring it would mark every Actions-only repo as "no CI" and let proposals through prematurely. |
| Unbounded per-PR polling task | **Single periodic in-process scanner** that wakes every `_CI_POLL_INTERVAL_SECONDS`, queries every PR in `pr_open` from SQLite, updates state. Hard `_CI_MAX_AGE_SECONDS` (default 6h) after which the PR is marked `ci_state="timed_out"`. | DB-driven recovery: API restarts mid-poll lose nothing. Single task is bounded by GitHub rate limits (we cap concurrent calls at 4). |
| `sys.exit(0)` restart with `systemd | docker | supervisor | custom` | **Five methods including `uvicorn-reload` and `noop`**. Default `noop` so a misconfigured flag never kills the API; `uvicorn-reload` (touching `app/_reload_sentinel.py`) is the dev-friendly path that works on this box right now. | We have no supervisor on this dev machine. `sys.exit` from a request handler with no supervisor would just stop the API. |
| `dependencies=[Depends(is_owner_role)]` | `_require_owner(db, app_user_id)` inside the body | Same reason as 73c — `is_owner_role` is a `bool` helper, not a FastAPI dependency. |
| Auto-merge unconditionally on CI pass | **Auto-merge only when the proposal has `auto_merge_on_ci_pass=True` AND the local sandbox is still within the 60s freshness window from Phase 73b**. Stale sandbox → `ci_state="passed_awaiting_sandbox"`, UI banner asks operator to re-run sandbox + click Merge. | Local sandbox is the actual safety net — we don't have remote CI for everything. Trusting CI alone over a stale local check is unsafe. |
| `auto_merge_on_ci` as a global flag | **Per-proposal column** (`auto_merge_on_ci_pass BOOLEAN`) flipped via `POST /{id}/auto-merge-on-ci` | Different proposals have different risk profiles; per-proposal opt-in is a simpler reasoning model. |

We additionally shipped a minimal `.github/workflows/python-ci.yml` so
`WAIT_FOR_CI=true` defaults are usable out of the box. Without it, every
self-improvement PR would block on "no CI exists for app/web yet".

---

## 2. Configuration

```bash
# Phase 73d — CI status polling for self-improvement PRs
NEXA_SELF_IMPROVEMENT_WAIT_FOR_CI=true                 # default true now that we ship a workflow
NEXA_SELF_IMPROVEMENT_CI_POLL_INTERVAL_SECONDS=30
NEXA_SELF_IMPROVEMENT_CI_MAX_AGE_SECONDS=21600         # 6h hard timeout

# Phase 73d — graceful restart after a remote merge lands
NEXA_SELF_IMPROVEMENT_AUTO_RESTART=false               # opt-in
NEXA_SELF_IMPROVEMENT_AUTO_RESTART_METHOD=uvicorn-reload
```

`AUTO_RESTART_METHOD` accepts:

| Method | Behaviour | Requirements |
|---|---|---|
| `uvicorn-reload` | Touches `app/_reload_sentinel.py` so a uvicorn `--reload` worker re-imports the application in-process. **Does not exit the process.** | API started with `uvicorn app.main:app --reload`. |
| `systemd` | `os._exit(0)` after the response flushes. Unit must restart on exit. | `systemd` unit with `Restart=always`. |
| `docker` | `os._exit(0)` after the response flushes. Container must restart on exit. | `--restart=always` (or compose equivalent). |
| `supervisor` | `os._exit(0)` after the response flushes. | Supervisord program with `autorestart=true`. |
| `noop` | Logs a warning and does nothing. **Default safe fallback.** | n/a |

The master switch (`NEXA_SELF_IMPROVEMENT_AUTO_RESTART`) is independent of
the method. If the master switch is `false`, even `/restart` returns 403 —
the operator restarts manually.

---

## 3. Backend pieces

### `app/services/self_improvement/github_client.py` — extended

New dataclasses `CiCheck`, `CiStatus` and method
`get_pr_ci_status(pr_number) -> CiStatus`. Three GitHub REST calls:

1. `GET /repos/{o}/{r}/pulls/{n}` — to resolve the head SHA (it can move
   between polls if the operator force-pushes).
2. `GET /repos/{o}/{r}/commits/{sha}/status` — legacy commit-statuses
   (Travis-style integrations).
3. `GET /repos/{o}/{r}/commits/{sha}/check-runs?per_page=100` — Actions
   check-runs.

Combined via `_combine_ci_states([...])`:

* Any leaf `pending` / `queued` / `in_progress` / `waiting` → `pending`.
* Any leaf `failure` / `cancelled` / `timed_out` / `action_required` /
  `stale` → `failure` (failure beats error).
* Any leaf `error` (and no failure) → `error`.
* All leaves `success` / `neutral` / `skipped` → `success`.
* Empty list → `pending` (we deliberately do **not** treat "no CI" as
  success; flip `WAIT_FOR_CI=false` to opt out).
* Unknown future GitHub conclusions → `pending` (safe default).

### `app/services/self_improvement/proposal.py` — extended

New columns added by the lazy idempotent migration in `_init_db`:

* `ci_state TEXT` — current value (see state list below).
* `ci_details TEXT` — JSON `{head_sha, total_count, checks: [{name, source, state, url}]}`.
* `ci_checked_at TEXT` — last poll timestamp (UTC).
* `ci_first_seen_pending_at TEXT` — used for the max-age timeout.
* `auto_merge_on_ci_pass INTEGER NOT NULL DEFAULT 0` — per-proposal opt-in.

`ci_state` values:

| Value | Meaning |
|---|---|
| `null` | Never polled. |
| `"pending"` | At least one leaf check is still running. |
| `"success"` | Every leaf concluded `success` / `neutral` / `skipped`. |
| `"failure"` | Some leaf concluded `failure` / `cancelled` / `timed_out`. |
| `"error"` | Some leaf concluded `error` (and no failure). |
| `"timed_out"` | Pending for longer than `_CI_MAX_AGE_SECONDS`; monitor stops polling. |
| `"passed_awaiting_sandbox"` | Monitor saw CI green AND `auto_merge_on_ci_pass=True` AND local sandbox stale. Auto-merge blocked; operator should re-run sandbox + click Merge. |

New writers: `set_ci_state(...)`, `set_auto_merge_on_ci(...)`, plus
`list_pr_open()` for the monitor.

### `app/services/self_improvement/ci_monitor.py` — new

Single periodic asyncio task owned by the API process. Started from
`app/main.py`'s lifespan; gated on `_ENABLED` + `_GITHUB_ENABLED` +
`_WAIT_FOR_CI`. Each scan:

1. `list_pr_open()` from SQLite.
2. `asyncio.gather` (sem-bounded at 4) `_poll_proposal` on each.
3. Update `ci_state` / `ci_details`. First-seen-pending stamped only the
   first time. Past max-age → `timed_out`.
4. On `success` AND `auto_merge_on_ci_pass`:
   * **Sandbox fresh** (≤60s) → call `merge_pull_request` directly,
     update status to `merged`, schedule restart if enabled.
   * **Sandbox stale** → mark `passed_awaiting_sandbox`, no merge.

Bounded by GitHub rate limits via `_MAX_CONCURRENT_POLLS=4`. Survives
restarts because all state is in SQLite.

### `app/core/restart.py` — new

* `restart_enabled()` / `restart_method()` resolve at request time.
* `perform_restart()` dispatches per method. Uses `os._exit(0)` (not
  `sys.exit`) for supervised methods so atexit hooks can't accidentally
  block the supervisor's restart.
* `schedule_restart(delay_s=1.0)` returns immediately so the calling
  request can flush its response, then fires `perform_restart` via
  `loop.call_later`. Used by both the merge endpoint and the dedicated
  `/restart` endpoint.
* `uvicorn-reload` mode writes a tiny module at `app/_reload_sentinel.py`
  with a fresh ISO timestamp; uvicorn's `--reload` watcher detects the
  change and re-imports the application in-process.

### `app/api/routes/self_improvement.py` — extended

| Endpoint | Auth | Behaviour |
|---|---|---|
| `GET /-/capabilities` | any web user | Now also returns `ci.{wait_for_ci,poll_interval_seconds,max_age_seconds}` and `auto_restart.{enabled,method,valid_methods}`. |
| `POST /{id}/merge-pr` | owner | Now ALSO checks `ci_state in {"success","passed_awaiting_sandbox"}` when `WAIT_FOR_CI=true`. Returns 409 `ci_required_but_state_<state>` otherwise. On success, schedules a restart if enabled. |
| `POST /{id}/refresh-ci` | owner | Manually re-poll GitHub CI for one proposal. Returns the full `CiDetails`. |
| `POST /{id}/auto-merge-on-ci` | owner | Body `{enabled: bool}` — flips the per-proposal flag. |
| `POST /restart` | owner | 403 if `_AUTO_RESTART=false`; otherwise schedules a restart and returns `{status:"scheduled"|"noop", method, delay_s}`. |

### `app/main.py` — extended lifespan

Started: `get_ci_monitor().start()` after the agent supervisor.
Stopped: `await get_ci_monitor().stop()` symmetrically on shutdown.
Both are no-ops if the feature gates aren't satisfied.

---

## 4. Web UI additions

`web/lib/api/self_improvement.ts` — new types `CiCheckSummary`, `CiDetails`,
`RefreshCiResponse`, `SetAutoMergeResponse`, `RestartResponse`. Three new
client functions: `refreshSelfImprovementCi`, `setSelfImprovementAutoMerge`,
`restartSelfImprovement`. `SelfImprovementProposal` extended with the five
new CI fields + `auto_merge_on_ci_pass`. `SelfImprovementCapabilities`
extended with `ci.*` and `auto_restart.{enabled,method,valid_methods}`.

`web/app/mission-control/(shell)/self-improvement/page.tsx`:

* Capabilities banner now shows `Wait for CI:` (with poll interval + max
  age) and `Auto-restart:` (with method + restart-now button if enabled).
* Per-row, when a proposal is in `pr_open` and GitHub is enabled:
  * **Refresh CI** button — manual re-poll.
  * **Auto-merge on CI pass / Disable auto-merge** toggle button — flips the
    per-proposal flag.
  * **CI badge** — colour-coded by state (`success` green, `failure`/`error`
    rose, `timed_out`/`passed_awaiting_sandbox` amber).
* **Stale-sandbox banner** — when `ci_state==="passed_awaiting_sandbox"`,
  an inline alert tells the operator to re-run sandbox + click Merge.

---

## 5. CI workflow

`.github/workflows/python-ci.yml`:

Two jobs that gate every PR against `main` touching `app/`, `tests/`,
`web/`, `requirements.txt`, the workflow file itself, or `.env.example`:

* **python**: `python -m compileall -q app` + `pytest -q` over the
  73-family subset (`test_self_improvement_phase73b.py`,
  `test_self_improvement_github_phase73c.py`,
  `test_self_improvement_ci_phase73d.py`,
  `test_self_healing_phase73.py`,
  `test_self_healing_wrap_up_phase73_5.py`).
* **web**: `npx tsc --noEmit` against the Next.js project.

`concurrency: cancel-in-progress: true` — a fresh push invalidates older
runs to keep the queue short. Both jobs install only what's needed,
backed by `actions/setup-python` + `actions/setup-node` caches.

If you don't want this CI workflow shipped, set
`NEXA_SELF_IMPROVEMENT_WAIT_FOR_CI=false` and the merge endpoint will skip
the CI gate entirely; the local sandbox remains the safety net.

---

## 6. End-to-end operator flow (full Genesis Loop)

1. Operator opens **Mission Control → Improvements**, fills the
   *Propose* form. LLM generates a unified diff. Status → `pending`.
2. Click **Sandbox** — `git worktree` apply + `compileall` + targeted
   `pytest`. Status stays `pending`; `sandbox_result.success=true`.
3. Click **Approve**. Status → `approved`.
4. Click **Open PR**. Backend pushes `self-improvement/<id>-<rand>` to
   `origin`, opens a PR. Status → `pr_open`. CI monitor begins polling.
5. (Optional) Click **Auto-merge on CI pass** to opt this PR into the
   automated path.
6. Workflows in `.github/workflows/python-ci.yml` (and any others) run
   on the PR. The monitor polls every 30s and updates `ci_state`.
7. **Branch a:** auto-merge enabled, sandbox fresh → monitor sees CI go
   green and merges automatically. Status → `merged`. If
   `_AUTO_RESTART=true` → API restarts via the configured method.
8. **Branch b:** auto-merge enabled, sandbox stale → `ci_state` becomes
   `passed_awaiting_sandbox`. Operator re-runs **Sandbox**, then clicks
   **Merge if mergeable** manually. Status → `merged`.
9. **Branch c:** auto-merge disabled → operator sees the green CI badge,
   clicks **Merge if mergeable** themselves.
10. **Rollback:** click **Revert via PR** any time after `merged`. Backend
    opens a fresh PR that reverts the merge commit; operator merges it
    on GitHub.

---

## 7. Tests — `tests/test_self_improvement_ci_phase73d.py`

37 tests, all green; no real network or `git` subprocesses; restart
endpoint patched to a sentinel-record instead of calling `os._exit`.

* `_combine_ci_states` — every branch including future-unknown values.
* `get_pr_ci_status` over `httpx.MockTransport` — combined statuses +
  check-runs, pending when an Actions check is `in_progress`, failure
  when an Actions check failed.
* `CiMonitor.scan_once` — pending/failure recording, max-age timeout,
  no auto-merge when flag off, auto-merge when flag on + sandbox fresh,
  `passed_awaiting_sandbox` when sandbox stale, GitHub errors are
  swallowed (one bad PR doesn't take the scan down).
* Router — capabilities exposes the new blocks, merge gates on `ci_state`
  when `WAIT_FOR_CI=true`, `passed_awaiting_sandbox` is treated as
  green for the manual click path, refresh-ci / auto-merge / restart
  endpoint contracts.
* Restart module — master flag honoured, `uvicorn-reload` writes the
  sentinel, `schedule_restart` actually fires the deferred call.

---

## 8. Files changed in 73d

| File | Action |
|---|---|
| `app/core/config.py` | Add `_WAIT_FOR_CI`, `_CI_POLL_INTERVAL_SECONDS`, `_CI_MAX_AGE_SECONDS`, `_AUTO_RESTART`, `_AUTO_RESTART_METHOD` |
| `.env.example` / `.env` | Sync the new vars with comments |
| `app/services/self_improvement/github_client.py` | Add `CiCheck`, `CiStatus`, `get_pr_ci_status`, `_combine_ci_states` |
| `app/services/self_improvement/proposal.py` | Move `APPLY_REQUIRES_FRESH_SANDBOX_S` here as canonical; add `_PHASE73D_COLUMNS` lazy migration; new dataclass fields; `set_ci_state`, `set_auto_merge_on_ci`, `list_pr_open` |
| `app/services/self_improvement/ci_monitor.py` | **new** — periodic in-process scanner with auto-merge handoff |
| `app/core/restart.py` | **new** — multi-method graceful restart |
| `app/api/routes/self_improvement.py` | Capabilities exposes `ci`+`auto_restart`; merge-pr CI gate; new `/{id}/refresh-ci`, `/{id}/auto-merge-on-ci`, `/restart` endpoints; merge-pr now schedules restart |
| `app/main.py` | Lifespan: start/stop ci_monitor |
| `web/lib/api/self_improvement.ts` | 5 new fields on Proposal, 2 new blocks on Capabilities, 3 new client functions + types |
| `web/app/mission-control/(shell)/self-improvement/page.tsx` | Capabilities banner with CI + restart blocks; per-row CI badge, Refresh CI button, auto-merge toggle, stale-sandbox banner; global Restart-API-now button |
| `.github/workflows/python-ci.yml` | **new** — minimal Python + web tsc CI on PRs against main |
| `tests/test_self_improvement_ci_phase73d.py` | **new** — 37 tests |
| `docs/PHASE73D_CI_AUTORESTART.md` | **new** — this document |

---

## 9. Deferred / out-of-scope

- **Branch-protection-aware merge.** We currently rely on `mergeable` +
  the AND of leaves; we don't yet inspect repo branch-protection rules
  to know which checks are "required" vs "optional". GitHub treats them
  the same in `combined_status` once they're configured as required, so
  for the `success` state this is moot.
- **Auto-revert on post-merge regression.** If the API restarts after a
  bad merge and the next health-check fails, we don't yet auto-open a
  revert PR. Combine with Phase 73's self-healing in a future phase.
- **Operator notifications when CI fails.** We update `ci_state` but
  don't push a Telegram message yet — surface via the dashboard CI badge
  for now.
- **Multi-repo support.** All settings target a single
  `<owner>/<repo>` pair. A future phase could let each proposal target
  a different repo.
