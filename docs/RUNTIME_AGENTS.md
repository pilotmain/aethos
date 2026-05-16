# Runtime agents (Phase 2 Step 9)

## Lifecycle

```text
spawned → active → busy → idle → recovering → suspended → expired | failed
```

- **aethos_orchestrator** — permanent system agent
- All other agents are runtime-managed, expire on TTL, suspend when idle too long

## APIs

- `GET /api/v1/mission-control/agents`
- Office topology: `GET /api/v1/mission-control/runtime` → `office`

## Metrics

Persisted in `aethos.json` → `runtime_agent_metrics`:

- `active_agents`, `busy_agents`, `expired_agents`, `recovered_agents`
- `agent_reassignment_count`, `agent_runtime_failures`
