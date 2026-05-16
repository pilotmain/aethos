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

## Phase 4 Step 8 — operational partitions and summaries

Truth evolution adds bounded cohesion without fragmenting orchestrator authority:

- `runtime_operational_partitions` — selective hydration targets (`live`, `operational`, `governance`, `intelligence`, `archive`)
- `runtime_enterprise_summarization` — summary-first MC rendering (`operational_summary`, `worker_summary`, etc.)
- `runtime_long_horizon` — compressed eras and governance windows
- `governance_operational_index` — timeline buckets and index health
- `runtime_calmness_integrity` — signal-over-noise discipline (extends `operational_calmness_lock`)
- `worker_operational_lifecycle` — spawn → archived → historical lineage
- `runtime_production_posture` — sustained operation and enterprise resilience scores

APIs: `GET /api/v1/runtime/partitions`, `/summaries`, `/eras`, `/production-posture`, `/calmness-lock`; MC `GET /governance/index`, `GET /workers/lifecycle`.
