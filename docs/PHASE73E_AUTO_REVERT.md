# Phase 73e — Post-Merge Auto-Revert (Genesis Loop closure)

> **Status:** safe-adapt v1, default OFF.
> **Depends on:** Phase 73 (self-healing supervisor + `mistakes` audit
> table), Phase 73c (GitHub client + `open_revert_pr`),
> Phase 73d (`merged` status + CI monitor + cooldown hook).
> **Adds:** auto-revert monitor, `/health/detailed`, per-proposal opt-out,
> 73d auto-merge cooldown gate.

The Genesis Loop must not leave the system broken. Phase 73e closes the
loop by **automatically opening a revert PR** when the rolling agent-audit
error rate spikes inside the observation window after a self-improvement
merge — restoring stability without forcing a human to babysit the
deploy.

---

## 1. Audit findings (what the literal spec assumed vs reality)

| Spec assumption | Reality at start of 73e | Adapted decision |
|---|---|---|
| ``app/api/routes/health.py`` already exists with detailed metrics | File exists but only returns ``{status, app, env}`` (4 lines) | **New** ``/health/detailed`` endpoint added to the same file |
| Pull error rate from ``agent_audit.db`` mistakes table | Table exists; ``agent_actions`` is the better source (has ``success`` column for every action, not just learned mistakes) | Use ``agent_actions`` aggregator in ``revert_monitor.fetch_error_rate_window`` |
| ``AgentSupervisor._check_agent_health`` is the natural integration point | Per-agent loop, not "did the API just regress" | Supervisor only **nudges** the monitor (``revert_monitor.kick_now()``); the monitor itself does its own evaluation |
| ``run_heartbeat_cycle`` already records last-heartbeat | Emits a runtime event but doesn't persist a queryable timestamp | Add ``system_state.touch_heartbeat()`` inside the cycle |
| Watch the most recent proposal in ``status="applied"`` | 73c made ``applied`` (local) and ``merged`` (remote) deliberately separate | Watch ``status="merged"`` (the remote-merge flow) |
| Revert PR can be auto-merged | Would create revert/un-revert flap loops on transient health spikes | **Open the revert PR only**; operator merges it (or 73d auto-merge-on-CI lands it) |
| ``/health`` non-200 → trigger revert | Liveness failures need an *escalation*, not a code revert (we can't even reach GitHub if the API itself is down) | Drop as a revert trigger; surface in ``/health/detailed`` for ops awareness |
| Optional canary scenario in v1 | Could itself fail and false-trigger | Defer |

The user explicitly approved the safe-adapt scope (`safe_adapt_73e`)
with `cooldown pauses only the 73d auto-merge-on-CI path` and
`UI per-row badge + per-proposal disable toggle + numeric health summary
in banner`.

---

## 2. Adapted scope — what 73e actually ships

### 2.1 Detection model

A merged proposal enters the **observation window** the moment it flips
to ``status="merged"`` (Phase 73c). Inside that window — default 5 min
(`NEXA_SELF_IMPROVEMENT_REVERT_MIN_OBSERVATION_WINDOW_SECONDS=300`) —
the monitor evaluates the most-recent merge once per
`NEXA_SELF_IMPROVEMENT_REVERT_HEALTH_CHECK_INTERVAL_SECONDS` (default 30 s):

A revert is fired only when **all** of these hold simultaneously:

1. ``post-restart grace`` has elapsed (default 60 s) — protects against
   the in-flight-request error blip after `uvicorn-reload`.
2. The rolling error count over the window is **≥ MIN_SAMPLE_SIZE**
   (default 10) — protects against tiny denominators.
3. The error rate over the window **> THRESHOLD** (default 0.3 = 30%).
4. The proposal is not opted-out (`auto_revert_disabled=false`).

When all gates pass, the monitor calls
``GitHubClient.open_revert_pr(merge_commit_sha, …)`` and records:

| Where | What |
|---|---|
| `self_improvement_proposals.status` | `revert_pr_open` |
| `self_improvement_proposals.revert_pr_number` / `_url` | the new PR |
| `self_improvement_proposals.auto_revert_state` | `"reverted"` |
| `system_state.last_auto_revert_at` | now (used by cooldown) |

The **revert PR is not auto-merged in v1.** Operator review is required
before landing the revert. (Operator can opt-in to 73d
auto-merge-on-CI for the revert PR, but that's a separate manual gate.)

### 2.2 Failure-criteria matrix (vs spec)

| Spec criterion | 73e behaviour | Why |
|---|---|---|
| Error rate > 30% over 5 min | **Triggers revert** when MIN_SAMPLE also met | Primary signal |
| API `/health` returns non-200 | **Escalation only** — surfaced in `/health/detailed` | Liveness failures need a different recovery path; opening a remote PR doesn't help |
| Heartbeat missing > 2 min | **Escalation only** — `heartbeat.stale=true` in `/health/detailed` | Same reasoning |
| Manual operator override (UI button) | Already covered by Phase 73c `Revert via PR` button on `merged` proposals | No new endpoint needed |

### 2.3 Cooldown semantics

After a revert fires, `last_auto_revert_at` is stamped. The 73d
**`ci_monitor`** consults that timestamp before triggering an
auto-merge-on-CI: if `now() - last_auto_revert_at` <
`NEXA_SELF_IMPROVEMENT_REVERT_COOLDOWN_MINUTES * 60`, the auto-merge
path is skipped (with an info log; the CI state is still recorded).

**Manual operator merges via `POST /{id}/merge-pr` are unaffected by
the cooldown.** This lets the operator land the operator-reviewed fix at
any time without disabling auto-revert.

Operator can effectively disable the cooldown gate by setting
`NEXA_SELF_IMPROVEMENT_REVERT_COOLDOWN_MINUTES=0`.

### 2.4 Per-proposal opt-out

Two ways to opt a proposal out of the watcher:

1. **Pre-merge:** `POST /api/v1/self_improvement/{id}/auto-revert
   {"disabled": true}` before the merge. The 73c merge handler seeds
   `auto_revert_state="disabled"` on flip-to-merged.
2. **Post-merge during the window:** same endpoint. The watcher checks
   `auto_revert_disabled` on every scan and short-circuits with
   `state="disabled"` when set.

`disabled=false` re-arms the watcher (without downgrading a terminal
state — `reverted` and `cleared` stay sticky).

---

## 3. Files touched

| File | Change |
|---|---|
| `app/core/config.py` | 7 new `nexa_self_improvement_*` settings |
| `.env.example`, `.env` | Synchronised the new env vars |
| `app/services/agent/system_state.py` | **New** — tiny `(key, value, updated_at)` table sitting next to `mistakes` in `agent_audit.db`; well-known keys for heartbeat / auto-revert / process-start |
| `app/services/scheduler/heartbeat.py` | Touch `last_heartbeat_at` on every cycle |
| `app/services/self_improvement/proposal.py` | New `_PHASE73E_COLUMNS` lazy migration, new fields + setters; `set_github_state(merged)` seeds `merged_at` + `auto_revert_state="watching"`; `list_recent_merged_within(window_seconds)` + `get_merged_age_seconds(id)` |
| `app/services/self_improvement/revert_monitor.py` | **New** — periodic scanner + `kick_now()` + `fetch_error_rate_window` aggregator |
| `app/services/self_improvement/ci_monitor.py` | Pause auto-merge-on-CI during 73e cooldown |
| `app/services/agent/supervisor.py` | On a high failure-rate alert, `revert_monitor.kick_now()` (best-effort) |
| `app/api/routes/health.py` | New `/health/detailed` endpoint |
| `app/api/routes/self_improvement.py` | `/-/capabilities` adds `auto_revert` block; new `POST /{id}/auto-revert` toggle; new `POST /-/revert-scan-now` owner trigger |
| `app/main.py` lifespan | `system_state.mark_process_started()` + `revert_monitor.start/stop()` (gated; no-op when feature off) |
| `web/lib/api/self_improvement.ts` | New `auto_revert` capability fields, new `auto_revert_*` proposal fields, `setSelfImprovementAutoRevert`, `revertScanNowSelfImprovement`, `getSystemHealthDetailed` |
| `web/app/mission-control/(shell)/self-improvement/page.tsx` | Per-row auto-revert badge + per-proposal disable toggle + numeric health summary + auto-revert "Scan now" button in capabilities banner |
| `tests/test_self_improvement_revert_phase73e.py` | **New** — 30+ unit/integration tests |
| `docs/PHASE73E_AUTO_REVERT.md` | This doc |

---

## 4. Configuration

```bash
# Phase 73e — Post-merge auto-revert on regression. Default off.
NEXA_SELF_IMPROVEMENT_AUTO_REVERT_ENABLED=false
NEXA_SELF_IMPROVEMENT_REVERT_HEALTH_CHECK_INTERVAL_SECONDS=30
NEXA_SELF_IMPROVEMENT_REVERT_ERROR_RATE_THRESHOLD=0.3
NEXA_SELF_IMPROVEMENT_REVERT_MIN_OBSERVATION_WINDOW_SECONDS=300
NEXA_SELF_IMPROVEMENT_REVERT_MIN_SAMPLE_SIZE=10
NEXA_SELF_IMPROVEMENT_REVERT_POST_RESTART_GRACE_SECONDS=60
NEXA_SELF_IMPROVEMENT_REVERT_COOLDOWN_MINUTES=30
```

To enable end-to-end (assumes Phase 73c GitHub flow is already configured):

1. Set `NEXA_SELF_IMPROVEMENT_AUTO_REVERT_ENABLED=true` and restart.
2. Verify in the Improvements page banner: `Auto-revert: on (≥10 mistakes,
   30% threshold, 5m window)`.
3. Verify `/api/v1/health/detailed` → `auto_revert.enabled=true`.

---

## 5. End-to-end flow (with auto-revert active)

```
Operator: propose → sandbox → approve → open-pr
   ↓
73d ci_monitor: poll CI, wait for green
   ↓
Operator: merge-pr (or 73d auto-merge-on-CI when sandbox is fresh)
   ↓
Phase 73c set_github_state(merged):
   - status = merged
   - merged_at = now
   - auto_revert_state = watching (unless pre-disabled)
   ↓
Phase 73e revert_monitor wakes every 30s during the next 5 min:
   error_rate over agent_actions in window > 30%? AND mistakes ≥ 10?
   AND post-restart grace elapsed?
       │
   ┌───┴───┐
  yes      no → mark watching, sleep
   │
   ▼
open_revert_pr(merge_commit_sha, …)
   - status = revert_pr_open
   - auto_revert_state = reverted
   - system_state.last_auto_revert_at = now (cooldown begins)
   ↓
73d ci_monitor: skips auto-merge-on-CI for the next 30 min
       (manual operator merges still work; revert PR is reviewable)
```

If the window elapses without firing, the watcher marks the proposal
`auto_revert_state="cleared"` on the next scan and stops polling.

---

## 6. UI

The Improvements page shows three new pieces of information:

1. **Capabilities banner** gains an `Auto-revert: on/off` line with the
   threshold and window summary, plus a `cooldown active — auto-merge
   paused` chip when the cooldown is in effect, plus a `Scan now` button
   (owner-only, runs the monitor immediately).
2. **Per-row badge** on every `merged` proposal: `Auto-revert: watching
   | reverted | cleared | disabled`, color-coded.
3. **Per-row "Disable auto-revert" / "Re-arm auto-revert" toggle** for
   proposals in the observation window. Lets the operator pre-disable a
   risky proposal even with the global flag on.
4. **Numeric health summary** in the capabilities banner showing the
   rolling error count + heartbeat age (sourced from `/health/detailed`).

The Phase 73c "Revert via PR" button is unchanged — operator can still
manually revert any merged proposal regardless of feature state.

---

## 7. Deferred items / non-goals

* **Auto-merging the revert PR.** Adding this in v1 risks a
  revert/un-revert flap loop when health recovers transiently. v2 may
  add an opt-in `auto_merge_revert_on_ci_pass` knob with a hard
  cap of 1 auto-merge per 24 h.
* **Canary scenario runner.** Risky as a primary signal — a canary that
  itself fails would false-trigger. v2 may add as a secondary signal
  ANDed with the error-rate criterion.
* **/health non-200 → revert** is intentionally **not** a trigger.
  Liveness failures escalate via the existing 73 supervisor escalation
  path; the auto-revert flow can't help when the API can't reach GitHub.
* **CEO Dashboard "Last improvement health" widget** — marked optional
  in spec; deferred per `ui_scope=self_improvement_only`.
* **Multi-merge causation.** When two proposals merge inside the window,
  the watcher reverts the most recent one. Smarter causal attribution
  is out of scope.

---

## 8. Test surface

`tests/test_self_improvement_revert_phase73e.py` covers:

* `SystemStateStore` — set/get, heartbeat age, cooldown gate, process-start.
* `ProposalStore.set_github_state` — merge flip seeds `merged_at` and
  `auto_revert_state`; respects pre-disabled.
* `ProposalStore.set_auto_revert_*` — disable/re-arm semantics, terminal
  state stickiness.
* `ProposalStore.list_recent_merged_within` — window scoping, includes
  `revert_pr_open` rows so the monitor can mark them cleared.
* `fetch_error_rate_window` — empty store, mixed success/failure rows.
* `RevertMonitor.scan_once` — every gate (grace, sample, threshold,
  disabled, no-merge-sha, GitHubError) plus the happy-path fire.
* `CiMonitor.scan_once` — pauses auto-merge during 73e cooldown,
  resumes when cooldown disabled.
* API: `/-/capabilities` exposes the `auto_revert` block;
  `/{id}/auto-revert` toggle owner-gated (403 for non-owner);
  `/-/revert-scan-now` returns `disabled` vs `scanned` correctly.
* `/health/detailed` shape, last-deploy reporting, in-cooldown reporting.
* `run_heartbeat_cycle` persists `last_heartbeat_at`.

---

## 9. Operational guidance

* Default off. Enable only after the GitHub flow (73c) and a CI workflow
  that exercises the changes are both in place.
* On a single-node deploy with `uvicorn-reload`, `_REVERT_POST_RESTART_GRACE_SECONDS`
  ≥ 60 is recommended to avoid the post-reload error blip.
* If you're seeing churn (revert fires that shouldn't), raise
  `_REVERT_MIN_SAMPLE_SIZE` first — it has the highest leverage on
  false positives, and a higher minimum just delays the revert by one
  scan tick when something's actually broken.
* `NEXA_SELF_IMPROVEMENT_REVERT_COOLDOWN_MINUTES=0` disables the
  auto-merge cooldown without disabling the watcher.
* Manual operator merges (`/merge-pr`) are intentionally never blocked
  by the cooldown.

---

## 10. Quick reference: status machine

```
pending ─→ approved ─→ pr_open ─→ merged ─→ revert_pr_open
                                     │
                                     └─ auto_revert_state ∈
                                        {watching, reverted, cleared, disabled}
```

* `merged → revert_pr_open` happens automatically (73e) **or** via the
  Phase 73c manual `Revert via PR` button.
* `auto_revert_state` is independent of the main status field and never
  blocks any operator action.
