# Mission Control (Phase 2 Step 8–10)

Mission Control is the operational surface for AethOS runtime state — not a simulation layer.

## Runtime APIs

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/mission-control/runtime` | Unified runtime payload |
| `GET /api/v1/mission-control/agents` | Dynamic runtime agents |
| `GET /api/v1/mission-control/tasks` | Task registry + queues |
| `GET /api/v1/mission-control/deployments` | Deployment identities + repairs |
| `GET /api/v1/mission-control/providers` | Provider inventory + actions |
| `GET /api/v1/mission-control/runtime-health` | Health color + pressure |
| `GET /api/v1/mission-control/runtime-events` | Bounded event tail |
| `GET /api/v1/mission-control/runtime-metrics` | Lightweight metrics |
| `WS /api/v1/mission-control/runtime/ws` | Live runtime events |
| `GET /api/v1/mission-control/runtime-trace` | Task → agent → provider trace chains |

Legacy unified payload: `GET /api/v1/mission-control/state` (includes `runtime_agents`, `office`, `brain_visibility`, `panels`).

## Step 10 — consolidated runtime truth

`build_runtime_truth()` in `app/services/mission_control/runtime_truth.py` is the authoritative path for agents, tasks, providers, deployments, health, plugins, privacy, and ownership. Panels and intelligence modules delegate to it.

Runtime health uses `healthy | warning | degraded | critical` with pressure flags (`queue_pressure`, `retry_pressure`, `deployment_pressure`, `recovery_active`). See `runtime_health_model.py`.

Events are aggregated for display (`aggregate_events_for_display`) to collapse repeated low-signal events, with severity prioritization.

## Step 11 — production cleanup

- **Cached truth:** `runtime_truth_cache.py` (5s TTL) backs all MC runtime APIs.
- **Lifecycle:** `runtime_lifecycle.py` sweeps stale repair contexts and trims deployment traces.
- **Traces:** `GET /api/v1/mission-control/runtime-traces` — ownership, repair, deployment, provider chains.
- **Plugins:** `build_plugin_health_panel()` exposes warnings, failures, permissions.
- **`/state` parity:** `build_execution_snapshot` embeds truth-derived `runtime_health`, `panels`, `operator_traces`.

## Live panels (Step 9)

`GET /api/v1/mission-control/runtime-panels` — runtime health, brain routing, provider operations, agents, privacy, recovery.

Events use categorized shape: `event_type`, `category`, `severity`, `correlation_id` (see [RUNTIME_EVENTS.md](RUNTIME_EVENTS.md)).

## The Office

Web route: `/mission-control/office` — lightweight cards for runtime agents (`active`, `busy`, `idle`, `recovering`, `failed`, `offline`).

## Dynamic agents

- **AethOS Orchestrator** is always present (`aethos_orchestrator`).
- Specialized agents are spawned on demand (e.g. repair) and expire when idle.

See `app/runtime/runtime_agents.py`.
