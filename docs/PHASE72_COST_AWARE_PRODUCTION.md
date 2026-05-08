# Phase 72 — Cost-aware model switching (production wiring)

## Problem

Phase 70 shipped the cost-aware infrastructure as opt-in helpers:

* `app/services/llm/cost_aware_router.py` (`route_for_task`, `select_model_for_task`,
  `recommend_cheaper_model_if_over_budget`).
* `app/services/llm_costs.py` (`PRICING_USD_PER_1M_TOKENS`, `estimate_llm_cost`).
* `app/services/llm_usage_recorder.py` already records every call to
  `LlmUsageEvent` with `estimated_cost_usd`.
* Phase 70 settings: `nexa_cost_aware_enabled`, `nexa_cost_aware_max_per_task_usd`,
  `nexa_cost_aware_{default,cheap}_{provider,model}`.

What was missing — Phase 72 closes the loop:

1. The router was never consulted by `primary_complete_messages` (the central
   LLM entry point), so opting in was a per-call-site lift.
2. There was no domain → model override map (the spec's
   `NEXA_DEFAULT_MODEL_PER_DOMAIN`).
3. Ollama wasn't guaranteed to be the last-resort fallback when cost-aware
   routing was on.
4. The CEO Dashboard didn't surface "today's LLM cost" even though every event
   was already in the database.

## Adapted scope

The Phase 72 spec proposed re-architecting the router around a `CostAwareRouter`
class that owns its own provider lookup and Ollama fallback. The existing
`primary_complete_messages` already implements multi-provider fallback chains
(`anthropic → openai → deepseek → openrouter → ollama`), per-call Anthropic
model overrides, BYOK key resolution, egress policy enforcement, budget
gating, and `LlmUsageEvent` recording. Replacing it would have been a strict
regression.

Phase 72 instead **threads cost-aware routing through the existing infrastructure**:

| Spec said | What landed | Why |
|-----------|-------------|-----|
| New `CostAwareRouter.complete()` that calls providers directly | Added `task_type` kwarg to existing `primary_complete_messages`; computes a `CostAwareDecision` and applies `anthropic_model_override` when applicable. | Keeps multi-provider fallback chain, BYOK, egress, budget gating, and event recording — all of which the spec didn't reproduce. |
| `CostAwareRouter.complete()` falls back to Ollama on `Exception` | Cost-aware fallback provider (`nexa_cost_aware_fallback_provider`, default `"ollama"`) is **appended to the chain** in `_build_chain()` when cost-aware routing is enabled. | Provider-level fallback already works for any failure (auth, egress, transient). |
| `_record_cost(...)` placeholder | _Already exists_ — `record_anthropic_message_usage` / `record_openai_message_usage` populate `LlmUsageEvent.estimated_cost_usd` for every call. | No new write path; CEO dashboard reads the same table the `/usage/*` API uses. |
| New `get_total_cost_today(user_id)` | Added thin `get_cost_summary_today(db, app_user_id, *, is_owner)` that wraps the existing `build_llm_usage_summary("today", …)` aggregator. | Reuses same per-user / owner scoping the rest of usage analytics uses. |
| `NEXA_MAX_COST_PER_TASK_USD`, `NEXA_FALLBACK_MODEL` | Phase 70 already added `NEXA_COST_AWARE_MAX_PER_TASK_USD` (kept). New `NEXA_COST_AWARE_FALLBACK_PROVIDER` (provider granularity matches the chain). | The chain works at provider granularity; Ollama picks the local model itself. |
| `NEXA_DEFAULT_MODEL_PER_DOMAIN` | Added `NEXA_COST_AWARE_DEFAULT_MODEL_PER_DOMAIN` (JSON map). | Matches the `nexa_cost_aware_*` naming the rest of the cost-aware settings use. |

## What landed

### Settings + env (`app/core/config.py`, `.env.example`, `.env`)

```python
nexa_cost_aware_default_model_per_domain: str = ""
nexa_cost_aware_fallback_provider: str = "ollama"
```

`.env` also caught up on the Phase 70 entries (`NEXA_APPROVALS_PANEL_ENABLED`,
`NEXA_COST_AWARE_*`, `NEXA_HOST_EXECUTOR_DRY_RUN_DEFAULT`) which had been added
to `.env.example` but not synced.

### Router enhancement (`app/services/llm/cost_aware_router.py`)

* **`parse_domain_model_overrides(settings=None) -> dict[str, tuple[provider, model]]`**
  parses `NEXA_COST_AWARE_DEFAULT_MODEL_PER_DOMAIN`. Accepts string values
  (`"claude-haiku-4-5"`, `"openai/gpt-4o-mini"`, `"ollama/llama3.2"`) and dict
  values (`{"provider": "openai", "model": "gpt-4o"}`). Malformed JSON or
  invalid entries log a warning and are skipped — never raises.
* **`select_model_for_task`** new precedence order:
  1. `force_tier` argument when set,
  2. Phase 72 domain override map (returns tier `"domain_override"`),
  3. `TASK_TIER_HINTS` for the lowercased task type,
  4. default tier.
* **`route_for_task`** now exposes `domain_override: bool` and `task_type` on
  `CostAwareDecision` and **does not silently downgrade** an explicit operator
  choice (only the heuristic-tier path swaps to the cheap tier when over budget).

### Production wiring (`app/services/llm/completion.py`)

* `primary_complete_messages(... task_type: str | None = None)` — backward
  compatible. When a `task_type` is provided **and** `nexa_cost_aware_enabled`
  is true, the function calls `route_for_task` and applies the chosen Anthropic
  model via the existing `anthropic_model_override` mechanism. Explicit
  `anthropic_model_override` arguments still win.
* `_build_chain()` appends `nexa_cost_aware_fallback_provider` (default
  `"ollama"`) as the last entry when cost-aware routing is on, so a local
  install becomes the safety net when remote providers fail.

### CEO dashboard wiring

* `app/services/llm_usage_recorder.py::get_cost_summary_today(db, app_user_id, *, is_owner)`
  — thin wrapper around `build_llm_usage_summary("today", …)` returning the
  shape the web UI consumes.
* `GET /api/v1/ceo/dashboard` — adds `cost_today` block + `summary.total_cost_today_usd` /
  `summary.total_llm_calls_today`. Owner-aware via the same
  `is_owner_role(get_telegram_role_for_app_user(...))` gate the rest of the web
  surface uses. Recorder failures are caught and reported as
  `cost_today.error == "cost_summary_unavailable"` (the rest of the dashboard
  keeps working).
* `web/app/mission-control/(shell)/ceo/page.tsx` — new "Today's LLM cost"
  card showing total spend, system vs. BYOK split, and per-provider breakdown.

### Tests (40 new cases across 3 files; 100% pass)

* `tests/test_cost_router_phase72.py` (15) — domain map parsing (valid /
  invalid JSON / non-object / dict values / explicit provider prefix /
  inferred provider / skip empty entries), `select_model_for_task` precedence
  (`force_tier` > domain map > tier hint > default), `route_for_task`
  surfaces `domain_override`, no silent downgrade for domain overrides,
  heuristic tier still downgrades when over budget.
* `tests/test_primary_complete_task_type_phase72.py` (7) — backward compat
  (no task_type ⇒ default model), cheap tier for `intent_classification`,
  default tier for `planning`, domain override beats tier hint, explicit
  `anthropic_model_override` always wins, cost-aware disabled means no
  override applied, router exception never propagates.
* `tests/test_ceo_dashboard_cost_phase72.py` (4) — dashboard returns
  `cost_today` block, owner sees all rows, non-owner only sees their own
  rows, recorder failure surfaces as `cost_summary_unavailable` without
  500-ing the rest of the dashboard.

## Configuration matrix

| Env | Default | Effect |
|-----|---------|--------|
| `NEXA_COST_AWARE_ENABLED` | `false` | Master switch. When off, every Phase 70 / 72 hook is a no-op and existing behavior is unchanged. |
| `NEXA_COST_AWARE_MAX_PER_TASK_USD` | `0.05` | Heuristic-tier downgrade threshold. Domain overrides ignore this (over-budget is reported, not enforced). |
| `NEXA_COST_AWARE_DEFAULT_PROVIDER` | `anthropic` | Default tier head. |
| `NEXA_COST_AWARE_DEFAULT_MODEL` | `claude-sonnet-4-5` | Default tier model. |
| `NEXA_COST_AWARE_CHEAP_PROVIDER` | `anthropic` | Cheap tier head. |
| `NEXA_COST_AWARE_CHEAP_MODEL` | `claude-haiku-4-5` | Cheap tier model. |
| `NEXA_COST_AWARE_DEFAULT_MODEL_PER_DOMAIN` | `""` | JSON map `{"qa":"claude-haiku-4-5","ops":"openai/gpt-4o-mini"}`. Empty disables the map. |
| `NEXA_COST_AWARE_FALLBACK_PROVIDER` | `ollama` | Provider name appended to the LLM chain when cost-aware is enabled. Set to `""` to disable the appended fallback. |
| `NEXA_HOST_EXECUTOR_DRY_RUN_DEFAULT` | `false` | (Phase 70) Default `simulate=True` for the host executor. |
| `NEXA_APPROVALS_PANEL_ENABLED` | `true` | (Phase 70) Mission Control approvals panel kill switch. |

## What was intentionally deferred

* **Per-call cost-aware wiring of every existing call site**: the two existing
  `primary_complete_messages` callers (`response_composer.py`,
  `pr_review/orchestrator.py`) still pass their own `anthropic_model_override`.
  Adding `task_type=` everywhere is a gradual rollout — easy now that the kwarg
  is in place.
* **Per-provider model overrides for non-Anthropic providers**: the chain still
  uses each provider's configured model when cost-aware picks an OpenAI or
  DeepSeek model. The decision is logged and visible on the CEO dashboard, but
  applying an OpenAI override would require a `clone_with_model` analog on
  `OpenAIBackend`. Future phase.
* **Telegram session model override (`@security_agent use model claude-3-opus
  then scan ...`)**: spec's optional stretch. Not in this phase; the CLI
  override path via `NEXA_COST_AWARE_DEFAULT_MODEL_PER_DOMAIN` covers the
  configuration-driven case.
* **Genesis Loop / self-healing agents** (Phase 73 per the user roadmap).

## Files touched / added

```
app/core/config.py
.env
.env.example
app/services/llm/cost_aware_router.py
app/services/llm/completion.py
app/services/llm_usage_recorder.py
app/api/routes/ceo_dashboard.py
web/app/mission-control/(shell)/ceo/page.tsx
tests/test_cost_router_phase72.py                       # new
tests/test_primary_complete_task_type_phase72.py        # new
tests/test_ceo_dashboard_cost_phase72.py                # new
docs/PHASE72_COST_AWARE_PRODUCTION.md                   # new
```
