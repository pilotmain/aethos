# Runtime performance (Phase 3 Step 12)

Mission Control reads authoritative runtime truth through **incremental slice hydration** instead of a monolithic cold rebuild on every request.

## Entry points

- `hydrate_runtime_truth_incremental()` — assembles truth from cached slices (`core`, `workers`, `intelligence`, `workspace`, `worker_memory`, `governance`, `derived`).
- `get_lightweight_slice()` — API fast path for single slices (workers, deployments, timeline, etc.).
- `get_cached_runtime_truth()` — full-truth TTL cache (default 30s via `AETHOS_TRUTH_CACHE_TTL_SEC`).

## Metrics on truth

- `runtime_performance` — hydration latency, payload bytes, slice cache hit rate.
- `hydration_metrics` — persisted in `aethos.json`.
- `operational_responsiveness` — target cached read budget.
- `runtime_scalability` — bounded arrays for deliverables/events.

## Env

| Variable | Default | Purpose |
|----------|---------|---------|
| `AETHOS_TRUTH_CACHE_TTL_SEC` | 30 | Full truth cache TTL |
| `AETHOS_TRUTH_SLICE_TTL_SEC` | 15 | Per-slice cache TTL |
| `AETHOS_TRUTH_MAINTENANCE_INTERVAL_SEC` | 60 | Throttled lifecycle sweeps during hydration |

## CLI

```bash
aethos runtime performance
aethos runtime cache
aethos runtime hydration
aethos runtime latency
aethos runtime scalability
aethos runtime payloads
aethos runtime pressure
```

Step 13 adds payload discipline and scalability health — see `docs/RUNTIME_SCALABILITY.md` and `docs/PAYLOAD_DISCIPLINE.md`.
