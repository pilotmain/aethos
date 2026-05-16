# Enterprise runtime confidence (Phase 3 Step 5)

Mission Control exposes a **runtime confidence** layer so operators can answer: *Can I trust this runtime right now?*

## API

`GET /api/v1/mission-control/runtime-confidence`

Derived from cached `build_runtime_truth()` — same TTL as other MC runtime APIs.

## Shape

```json
{
  "runtime_confidence": {
    "health": "healthy",
    "uptime_hours": 72,
    "restart_count": 1,
    "active_recoveries": 0,
    "provider_failures_24h": 0,
    "plugin_failures_24h": 0
  },
  "operational_stability": { "status": "healthy", "summary": "..." },
  "provider_reliability": { "unstable_providers": [], "summary": "..." },
  "repair_confidence": { "success_rate": 0.9, "confidence": "high" },
  "deployment_confidence": { "success_rate": 0.95 },
  "brain_routing_confidence": { "routing_confidence": 0.85 },
  "marketplace_stability": { "trust": "high" },
  "runtime_cost": { "note": "Lightweight estimates" },
  "onboarding": { "readiness_score": 0.8, "checks": [] },
  "ownership": { "operator_id": "...", "deployment_count": 0 },
  "scalability": { "truth_build_ms": 12, "cache_hit_rate": 0.5 }
}
```

## Health states

`healthy` · `warning` · `degraded` · `critical` · `recovering`

## Implementation

`app/services/mission_control/runtime_confidence.py`
