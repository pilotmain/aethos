# Runtime cohesion (Phase 3 Step 11)

All Mission Control operational views derive from **`build_runtime_truth()`** via **`get_cached_runtime_truth()`** (5s TTL).

## Cohesion bundle (`runtime_cohesion`)

- `operational_views` — workers, tasks, deployments, providers, packs, recommendations, governance, continuity, risk, deliverables, workspace
- `enterprise_operational_health` — ten category health model
- `unified_operational_timeline` — merged governance + recommendations + risk
- `operational_summary` — headline + coordination + cohesion report
- `worker_collaboration` — enriched orchestrator chains

## APIs

- `GET /api/v1/mission-control/runtime/health`
- `GET /api/v1/mission-control/runtime/timeline`
- `GET /api/v1/mission-control/operational-summary`
- `GET /api/v1/mission-control/runtime/cohesion`
- `GET /api/v1/mission-control/governance/summary`

## CLI

```bash
aethos runtime health|timeline|recommendations|workers
aethos operational summary
aethos governance summary
aethos workspace health
```
