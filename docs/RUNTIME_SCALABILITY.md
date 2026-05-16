# Runtime scalability (Phase 3 Step 13)

Enterprise-scale operational visibility with bounded payloads, paginated workers, and searchable governance.

## Truth keys

- `runtime_scalability_health` — pressure, buffer size, cache hit rates
- `payload_discipline` — bytes, caps, collapse counts
- `operational_pressure` — queue/retry/deployment pressure
- `runtime_query_efficiency` — cache reuse and build latency
- `governance_scalability` — audit entry counts and search support
- `enterprise_operational_views` — summarized deployment/provider/worker overviews

## Env

| Variable | Default |
|----------|---------|
| `AETHOS_TRUTH_PAYLOAD_MAX_BYTES` | 400000 |
| `AETHOS_TIMELINE_PAGE_MAX` | 48 |
| `AETHOS_WORKER_SUMMARY_PAGE_SIZE` | 24 |

## APIs

- `GET /mission-control/runtime/scalability`
- `GET /mission-control/runtime/workers/summaries?page=&page_size=`
- `GET /mission-control/governance/search?q=`
- `GET /mission-control/governance/filter?kind=&actor=…`
- `GET /mission-control/timeline/window?offset=&limit=`
- `GET /mission-control/timeline/search?q=`
