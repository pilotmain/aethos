# Mission Control (Phase 2 Step 8)

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

Legacy unified payload: `GET /api/v1/mission-control/state` (includes `runtime_agents`, `office`, `brain_visibility`).

## The Office

Web route: `/mission-control/office` — lightweight cards for runtime agents (`active`, `busy`, `idle`, `recovering`, `failed`, `offline`).

## Dynamic agents

- **AethOS Orchestrator** is always present (`aethos_orchestrator`).
- Specialized agents are spawned on demand (e.g. repair) and expire when idle.

See `app/runtime/runtime_agents.py`.
