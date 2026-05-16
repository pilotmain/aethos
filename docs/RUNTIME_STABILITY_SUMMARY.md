# Runtime stability summary

## Discipline (bounded state)

- Event buffer capped (`runtime_event_buffer`)
- Aggregated display events (`aggregate_events_for_display`)
- Cached runtime truth (5s TTL)
- Governance timeline capped (default 32 entries)
- Discipline metrics: payload bytes, truth build ms, timeline build ms

## Stability signals

- `runtime_stability` — restart cycles, pressure events
- `runtime_continuity` — recovery attempts/successes
- `runtime_metrics` — deployment/retry counters
- Consolidated health — `healthy | warning | degraded | critical | recovering`

## Recovery

Runtime agents recover after restart; repair contexts tracked per project; governance timeline records repair and deployment narratives.

See [ENTERPRISE_RUNTIME_CONFIDENCE.md](ENTERPRISE_RUNTIME_CONFIDENCE.md).
