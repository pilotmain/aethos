# Automation pack runtime (Phase 3 Step 10)

Operator-triggered pack execution — **not** hidden background automation.

## Pack runtime shape

`pack_id`, `capabilities`, `trust_tier`, `execution_scope`, `execution_history`, `runtime_health`, `governance_state`, `operational_metrics`

## Run pack

```http
POST /api/v1/mission-control/automation-packs/{pack_id}/run
```

```bash
aethos marketplace run-pack <pack_id>
```

Executions persist in `automation_pack_executions` with trace chain:
`operator → orchestrator → automation_pack → result`
