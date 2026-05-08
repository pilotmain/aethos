# Phase 73 — Self-healing agents (Genesis Loop)

## Problem

Agents need to recover from their own failures without a human in the loop.
Phase 28 (heartbeat) and Phase 37 (`AgentSupervisor`) shipped enough
infrastructure to *detect* trouble (success-rate alerts, stuck-busy resets,
audit logs) but no *response*: a wedged agent stayed wedged until someone
called `/agents/{id}/resume` and a flapping LLM stayed broken until somebody
swapped the provider.

## Adapted scope

The Phase 73 spec assumed several things that don't hold in this codebase:

| Spec assumption | Reality | Adaptation |
|---|---|---|
| "Phase 28 `AgentHeartbeatService` …" | `app/services/agent/heartbeat.py` is just an event-name constant; the loop lives in `AgentSupervisor._check_agent_health` (Phase 37). | Build the self-healing pass on the existing supervisor tick; no new background service. |
| Add `error_count` / `last_error` columns to `SubAgent` | `SubAgent.metadata: dict[str, Any]` is already persisted as JSON. | Store `recovery_attempts` / `last_recovery_strategy` / `last_recovery_at` / `fallback_llm` inside `metadata`. No schema migration. |
| "subprocess hung → kill and restart the agent's worker" via `restart_agent_worker` | `SubAgent` is *"a logical sub-agent record (not a separate OS process)"*. | Replace with realistic primitives: BUSY → IDLE state reset, clear `current_task`, set per-agent fallback LLM flag, escalate when nothing else worked. |
| Separate SQLite at `data/mistake_memory.db` | We already have `data/agent_audit.db` with the same connection-per-call pattern. | New `mistakes` table inside the same DB. One file, one schema migration. |
| `agent.parent_chat_id != user_id` for the API auth check | Web user ids are `tg_<id>`, registry agents use `parent_chat_id`. The rest of `/agents/*` uses `_api_orchestration_scopes` + `_ensure_agent_in_scopes`. | Reuse those helpers so cross-scope users get a proper 404 and same-scope users get their agent. |
| `from app.services.llm import get_llm` for diagnosis | `get_llm()` returns a callable (or `None`) and bypasses cost-aware routing. | Use `primary_complete_messages([...], task_type="diagnosis")` so Phase 72's cost-aware router puts diagnosis on the cheap tier (Haiku) automatically. |
| `nexa_agent_escalation_chat_id` | Doesn't exist; `send_telegram_message(chat_id, text)` does. | Added. Escalation only fires when the chat id is set; otherwise the alert is logged + recorded. |

## What landed

### Settings + env (`app/core/config.py`, `.env.example`, `.env`)

```python
nexa_self_healing_enabled: bool = True
nexa_agent_escalation_chat_id: str = ""
nexa_agent_max_auto_recovery_attempts: int = 3
nexa_agent_failure_threshold: int = 3
nexa_agent_failure_window_minutes: int = 60
```

Synced into both `.env.example` and `.env` per the workspace rule.

### `app/services/agent/learning.py` (new)

`MistakeMemory` backed by a new `mistakes` table inside the existing
`data/agent_audit.db`. Schema:

```sql
CREATE TABLE mistakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    error TEXT,
    cause_class TEXT,
    recovery_strategy TEXT,
    recovery_succeeded INTEGER NOT NULL DEFAULT 0,
    context TEXT,
    occurred_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

`fingerprint_error()` collapses numbers / hex blobs / quoting so two formatted
exceptions with the same shape land in the same bucket
(`"Anthropic 429 rate_limit on req 12345abcdef"` and
`"anthropic 503 rate_limit on req 99999bcdef"` both fingerprint to a comparable
string). `get_similar_mistakes()` returns same-fingerprint or substring-match
rows. `successful_strategy_for(fingerprint)` returns the most recent recovery
strategy that worked, so the recovery handler can prefer a known-good fix.

Embedding-based similarity is deferred (Phase 73b).

### `app/services/agent/self_diagnosis.py` (new)

Heuristic-first classifier. Reads recent failures from the existing
`AgentActivityTracker` and bins them into:

| Cause class | When |
|---|---|
| `no_recent_failures` | Tracker shows no failures in the rolling window. |
| `state_corrupted` | Agent is BUSY past 600s, OR error text mentions stuck/deadlock language. |
| `repeated_llm_error` | ≥50% of recent errors mention known LLM patterns (rate limit, 429, timeout, 503, anthropic/openai error strings). |
| `transient` | Failures exist but fingerprint to ≥2 distinct buckets. |
| `unknown` | Anything else with a non-empty failure list. |

Optional LLM summary via `primary_complete_messages(task_type="diagnosis")` —
informational only. The heuristic always picks `cause_class`; a missing LLM
key never breaks the recovery decision.

### `app/services/agent/recovery.py` (new)

`RecoveryHandler.attempt(agent, diagnosis)` dispatches to one of:

| Strategy | Effect |
|---|---|
| `state_reset` | BUSY/ERROR → IDLE; clear `metadata.current_task` (in-place mutation since `patch_agent` only merges keys). |
| `llm_fallback` | Set `metadata.fallback_llm = nexa_cost_aware_fallback_provider` (default `"ollama"`); also runs `state_reset`. |
| `pause` | Set status to PAUSED. |
| `none` / `capped` | No-op (no failures or attempt cap reached). |

Per-agent `metadata.recovery_attempts` is incremented on every attempt and
capped at `nexa_agent_max_auto_recovery_attempts`. When the cap is hit the
result is marked `escalate=True` and the supervisor escalates instead of
looping. When mistake memory has a known-good strategy for the same
fingerprint, that strategy wins over the heuristic default.

`RecoveryHandler.reset_recovery_attempts(agent_id)` clears the counters — used
by the manual recover endpoint and intended for the executor's "task
succeeded" path in a follow-up phase.

### `app/services/agent/supervisor.py` (enhance)

`_check_agent_health` now calls `_run_self_healing(agent, stats)` for every
agent each tick when `nexa_self_healing_enabled` is true:

1. Pull recent failures from the tracker; skip if `< nexa_agent_failure_threshold`.
2. `SelfDiagnosis.diagnose(agent)`.
3. Tracker breadcrumb (`self_heal_diagnosis`).
4. `RecoveryHandler.attempt(agent, diagnosis)` — handler writes its own
   `self_heal_recovery` row and the mistake-memory row.
5. If `result.escalate`, `_escalate_self_heal(agent, diag, result)`:
   logs + writes `self_heal_escalation` to the tracker; sends a Telegram
   message only when `nexa_agent_escalation_chat_id` is set.

All branches are caught — a self-healing failure never breaks the supervisor
loop.

### `app/api/routes/agent_health.py` (new) + wired into `app/main.py`

| Method + path | Auth | Purpose |
|---|---|---|
| `GET /api/v1/agent/health/{agent_id}` | scope-only (any web user with the agent in their orchestration scope) | Status, last_active, recovery metadata, recent failure rollup. |
| `POST /api/v1/agent/health/{agent_id}/diagnose` | scope + owner | Run heuristic + optional LLM diagnosis; no state change. |
| `POST /api/v1/agent/health/{agent_id}/recover` | scope + owner | Diagnose + recover (mutates agent metadata). |

All three return 404 when `nexa_self_healing_enabled` is false. The owner
gate uses the same `is_owner_role(get_telegram_role_for_app_user(...))`
pattern marketplace mutations use.

### CEO Dashboard web UI

Each agent row in the existing roster gets a small health badge fetched lazily
from `GET /api/v1/agent/health/{id}`:

- `healthy` (green) — 0 failures in 24h.
- `N fails/24h` (amber) — below threshold.
- `N fails/24h` (rose) — at or above threshold.
- Appended `· recovered K×` when prior recovery attempts were registered.
- Appended `· fb:<provider>` when the agent has an active fallback LLM flag.

Hover tooltip shows raw counts + max attempts. No new panel; the page stays
focused on the agent roster + cost card.

### Tests (24 new cases, all green)

`tests/test_self_healing_phase73.py` covers, with injected fakes (no real DB,
no LLM):

* `learning` — fingerprint collapses numbers/hex; round-trip insert + similar
  match; `successful_strategy_for`; empty-fingerprint guard.
* `self_diagnosis` — no_failures short-circuit; state_corrupted (BUSY too
  long); repeated_llm_error; transient; unknown; LLM failure never breaks the
  call.
* `recovery` — none/cap/state_reset/llm_fallback strategies; metadata clears
  on state_reset; cap escalates; mistake-memory known-good strategy wins;
  reset_recovery_attempts.
* `supervisor._run_self_healing` — skip below threshold; full diagnose +
  recover above threshold; escalation logs even when chat id unset.
* `/api/v1/agent/health/*` — out-of-scope returns 404; in-scope returns
  payload; non-owner blocked from diagnose; owner runs full recover; disabled
  flag returns 404.

Broader sweep of 326 tests (lockdown + Phase 70/71/72/73) green; tsc clean.

## Deferred (documented for follow-up phases)

* **Phase 73b — self-improvement.** Agents proposing diffs/config changes to
  AethOS itself. Needs an approval pipeline + sandbox + diff review UI;
  substantial separate phase.
* **Embedding-based mistake similarity.** v1 uses fingerprint substring
  match; embedding lookup would let semantically related errors cluster.
* **Subprocess restart.** Agents are in-process today; if/when they become
  real workers we'd add a `STRATEGY_PROCESS_RESTART`.
* ~~**Auto-clear `recovery_attempts` on next successful task.**~~ ✅ Landed
  in Phase 73.5 — `AgentExecutor.execute` calls
  `RecoveryHandler.reset_recovery_attempts(agent_id)` on the success path
  (best-effort, swallows handler errors).
* ~~**Mission Control "Diagnose" / "Recover" buttons.**~~ ✅ Landed in
  Phase 73.5 — buttons appear inside each agent row when
  `self_healing.enabled` is reported by the health endpoint, with an inline
  status banner showing the diagnosis cause + recovery strategy + result
  (and an explicit "Dismiss" affordance).

## Phase 73.5 — wrap-up addendum

### What landed

| File | Change |
|---|---|
| `app/services/sub_agent_executor.py` | After `self.registry.touch_agent(agent.id)` on the success path, calls `get_recovery_handler().reset_recovery_attempts(agent.id)` inside a `try/except` so a flapping-then-recovered agent gets its quota back without escalating on the next minor hiccup. Failures inside the recovery handler never propagate. |
| `web/app/mission-control/(shell)/ceo/page.tsx` | Per-agent "Diagnose" / "Recover" buttons inside the existing roster row, gated by `h?.self_healing.enabled` returned by `/agent/health/{id}`. Inline status banner with `ok` / `warn` / `err` tones reports the diagnosis cause class + recovery strategy + attempt count + escalation flag. Button labels switch to "Diagnosing…" / "Recovering…" while the request is in flight, and other rows remain interactive (state is keyed by `{agentId, kind}`). |
| `tests/test_self_healing_wrap_up_phase73_5.py` | 4 new tests: executor clears `recovery_attempts` on success, idempotent when already zero, swallows recovery-handler exceptions, leaves the counter alone on a failed task. |

### Notes for future maintainers

* The recovery handler is a module-level singleton
  (`app.services.agent.recovery._recovery_handler`). Earlier Phase 73 tests
  inject fakes into it; tests that touch the executor's auto-clear path must
  reset the singleton in their fixture (see `_reset_state` in
  `tests/test_self_healing_wrap_up_phase73_5.py`).
* The CEO page's Diagnose/Recover buttons hit the existing owner-gated
  endpoints — non-owner users will see a 403 surfaced as the inline error
  banner, not as a silent failure.

## Files touched / added

```
app/core/config.py
.env
.env.example
app/services/agent/learning.py            # new
app/services/agent/self_diagnosis.py      # new
app/services/agent/recovery.py            # new
app/services/agent/supervisor.py          # enhanced
app/api/routes/agent_health.py            # new
app/main.py                               # router wiring
web/app/mission-control/(shell)/ceo/page.tsx
tests/test_self_healing_phase73.py        # new (24 cases)
docs/PHASE73_SELF_HEALING.md              # new
```

### Phase 73.5 wrap-up — additional files touched

```
app/services/sub_agent_executor.py        # success-path reset_recovery_attempts hook
web/app/mission-control/(shell)/ceo/page.tsx  # Diagnose/Recover buttons + flash banner
tests/test_self_healing_wrap_up_phase73_5.py  # new (4 cases)
docs/PHASE73_SELF_HEALING.md              # this addendum
```

## Configuration matrix

| Env | Default | Effect |
|-----|---------|--------|
| `NEXA_SELF_HEALING_ENABLED` | `true` | Master switch. When false, the supervisor tick skips self-healing entirely and the API endpoints 404. |
| `NEXA_AGENT_ESCALATION_CHAT_ID` | `""` | Telegram chat id for escalation alerts. Empty = log + audit only (no Telegram send). |
| `NEXA_AGENT_MAX_AUTO_RECOVERY_ATTEMPTS` | `3` | Cap on per-agent recovery attempts before forced escalation. |
| `NEXA_AGENT_FAILURE_THRESHOLD` | `3` | Failures within the rolling window before self-healing fires. |
| `NEXA_AGENT_FAILURE_WINDOW_MINUTES` | `60` | Rolling window for the failure threshold. |
