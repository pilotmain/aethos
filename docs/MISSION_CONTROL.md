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

- **Cached truth:** `runtime_truth_cache.py` (default 30s TTL) + incremental slices in `runtime_hydration.py` back MC runtime APIs.
- **Trust (Step 14):** execution visibility, operational trust score, unified governance timeline, escalations — see `docs/OPERATIONAL_TRUST_MODEL.md`.
- **Cohesion (Step 15):** unified runtime identity, operator experience, calmness, narratives — see `docs/MISSION_CONTROL_COHESION.md` and `docs/ENTERPRISE_OPERATOR_EXPERIENCE.md`.
- **Readiness (Step 16):** truth lock, enterprise readiness, production hardening — see `docs/ENTERPRISE_READINESS.md` and `docs/MISSION_CONTROL_FINALIZATION.md`.
- **Lifecycle:** `runtime_lifecycle.py` sweeps stale repair contexts and trims deployment traces.
- **Traces:** `GET /api/v1/mission-control/runtime-traces` — ownership, repair, deployment, provider chains.
- **Plugins:** `build_plugin_health_panel()` exposes warnings, failures, permissions.
- **`/state` parity:** `build_execution_snapshot` embeds truth-derived `runtime_health`, `panels`, `operator_traces`.

## Step 3 — plugin marketplace

- Web: `/mission-control/plugins` — install, uninstall, health, permissions.
- APIs: `/api/v1/marketplace/plugins`, `/install`, `/uninstall`, `/upgrade`.
- Runtime truth includes `marketplace`, `operational_intelligence`, `workspace_intelligence`, `runtime_governance`.

## Step 3 — production polish

- **`GET /mission-control/office`** — orchestrator, workers, pressure, privacy, signal events (from truth).
- Agents: `aethos_orchestrator` is `persistent: true`; workers are ephemeral (`persistent: false`).
- Panels use cached truth; discipline metrics track payload size and cache hit rate.
- Cohesion: `mission_control_cohesion.build_cohesion_report()`.

## Live panels (Step 9)

`GET /api/v1/mission-control/runtime-panels` — runtime health, brain routing, provider operations, agents, privacy, recovery.

Events use categorized shape: `event_type`, `category`, `severity`, `correlation_id` (see [RUNTIME_EVENTS.md](RUNTIME_EVENTS.md)).

## Phase 3 Step 7 — worker intelligence

- **Operational memory** per worker (`worker_memory`) — bounded tasks, outputs, failures, workspace context.
- **Deliverables** persist after worker expiration (`worker_deliverables`, searchable API).
- **Follow-ups** — `what did you find?`, `show deployment reports`, session-linked workers.
- **Continuations** — recover interrupted tasks after runtime restart.
- See [RUNTIME_WORKER_MEMORY.md](RUNTIME_WORKER_MEMORY.md).

## Phase 3 Step 6 — orchestrator agent visibility

- Registry spawns link to **runtime workers** (`runtime_agent_handles`, `agent_outputs`, `task_registry`).
- Chat answers agent result questions from **runtime truth** (never "no visibility" for created agents).
- `/subagent show|tasks|results` and gateway routing via `agent_runtime_truth.py`.
- See [SUBAGENT_RUNTIME_UNIFICATION_AUDIT.md](SUBAGENT_RUNTIME_UNIFICATION_AUDIT.md).

## Phase 3 Step 5 — commercial readiness

- **`GET /mission-control/runtime-confidence`** — uptime, restarts, 24h failures, stability, provider/repair/deployment confidence, onboarding checks, cost estimates.
- Office shows a **Runtime confidence** summary card.
- Health states include **`recovering`**.
- Governance timeline includes deployments and automation packs; timeline build tracked in discipline metrics.

See [ENTERPRISE_RUNTIME_CONFIDENCE.md](ENTERPRISE_RUNTIME_CONFIDENCE.md), [OPERATIONAL_TRUST_MODEL.md](OPERATIONAL_TRUST_MODEL.md), [COMMERCIAL_POSITIONING.md](COMMERCIAL_POSITIONING.md).

## Phase 3 Step 4 — product cohesion

- **Navigation:** Office, Runtime, Deployments, Providers, Marketplace, Privacy, Governance, Settings (see [UI_DEPRECATION_PLAN.md](UI_DEPRECATION_PLAN.md)).
- **Plugins vs skills:** [PLUGIN_VS_SKILL_ARCHITECTURE.md](PLUGIN_VS_SKILL_ARCHITECTURE.md).
- **`GET /mission-control/governance`** — operational timeline (`build_governance_timeline`).
- **`GET /mission-control/runtime-workers`** — worker role, assignment, ownership chain.
- **`GET /mission-control/runtime-workers/{id}`** — detail (memory, deliverables, continuations sub-routes).
- **`GET /mission-control/deliverables`** — searchable deliverables; export via `/deliverables/{id}/export`.
- **Mission Control → Deliverables** (secondary nav) — lightweight list, filter, export.
- **`GET /mission-control/workspace-intelligence`**, **`/workspace-risks`**, **`/research-chains`**, **`/operator-continuity`**, **`/worker-collaboration`** — Step 9 workspace intelligence.
- **Mission Control → Workspace** (secondary nav) — projects, risk, research continuity.
- **`GET /mission-control/runtime-recommendations`**, **`/enterprise-runtime`**, **`POST /automation-packs/{id}/run`** — Step 10 enterprise intelligence.
- **Mission Control → Insights** — operational intelligence, recommendations, pack run (operator-triggered).
- **Step 11 cohesion** — `GET /runtime/health`, `/runtime/timeline`, `/operational-summary`, `/runtime/cohesion`, `/governance/summary`; all views derive from cached `build_runtime_truth()`.
- **Readable summaries** on truth: `readable_summaries` (repairs, provider actions, health sentence).
- **CEO** (`/mission-control/ceo`) deprecated in favor of Office.

## Phase 4 Step 8 — production runtime convergence

Summary-first runtime surfaces with bounded long-horizon continuity, operational partitions, and calmness discipline. All keys attach via `apply_runtime_evolution_step8_to_truth()`; `enterprise_overview.phase` is `phase4_step8`.

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/runtime/summaries` | Enterprise summaries (operational, worker, governance, deployment, provider, continuity) |
| `GET /api/v1/runtime/partitions` | Live / operational / governance / intelligence / archive partition state |
| `GET /api/v1/runtime/eras` | Long-horizon operational eras and governance windows |
| `GET /api/v1/runtime/production-posture` | Production readiness and sustained-operation scoring |
| `GET /api/v1/runtime/calmness-lock` | Calmness integrity, noise score, escalation visibility |
| `GET /api/v1/mission-control/governance/index` | Bounded governance index health and query cost |
| `GET /api/v1/mission-control/workers/lifecycle` | Worker lifecycle maturity, trust, lineage |

CLI: `aethos runtime eras|summaries|partitions|posture|calmness`, `aethos governance index`, `aethos workers lifecycle`.

Docs: [RUNTIME_LONG_HORIZON.md](RUNTIME_LONG_HORIZON.md), [ENTERPRISE_RUNTIME_SUMMARIZATION.md](ENTERPRISE_RUNTIME_SUMMARIZATION.md), [OPERATIONAL_PARTITIONS.md](OPERATIONAL_PARTITIONS.md), [GOVERNANCE_INDEXING.md](GOVERNANCE_INDEXING.md), [RUNTIME_CALMNESS_LOCK.md](RUNTIME_CALMNESS_LOCK.md), [WORKER_LIFECYCLE_GOVERNANCE.md](WORKER_LIFECYCLE_GOVERNANCE.md), [PRODUCTION_RUNTIME_POSTURE.md](PRODUCTION_RUNTIME_POSTURE.md).

Runtime overview (`/mission-control/runtime-overview`) loads `/runtime/summaries` first for a summary headline before detail panels.

## The Office

Web route: `/mission-control/office` — lightweight cards for runtime agents (`active`, `busy`, `idle`, `recovering`, `failed`, `offline`). Progressive Office stream and partition-aware hydration (Step 7) remain; Step 8 adds calmness lock and enterprise summaries without analytics-wall noise.

## Dynamic agents

- **AethOS Orchestrator** is always present (`aethos_orchestrator`).
- Specialized agents are spawned on demand (e.g. repair) and expire when idle.

See `app/runtime/runtime_agents.py`.
