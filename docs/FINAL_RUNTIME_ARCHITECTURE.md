# Final runtime architecture (Phase 4 Step 13)

```text
Events → runtime_state → build_runtime_truth()
         → hydrate_runtime_truth_incremental()
         → apply_runtime_evolution (steps 1–13)
         → enterprise_overview
         → Mission Control / CLI / Telegram surfaces
```

## Truth ownership

| Concern | Owner |
|--------|--------|
| Raw events | `runtime_state` |
| Hydrated truth | `build_runtime_truth` + cache |
| Evolution bundle | `runtime_evolution.py` |
| Launch lock | `runtime_evolution_step13.py` |
| Recovery copy | `runtime_recovery_experience.py` |
| Calmness metrics | `enterprise_calmness_metrics.py` |

## Intentional duplicates

Documented in `runtime_duplication_lock` on truth and [RUNTIME_DUPLICATION_LOCK.md](RUNTIME_DUPLICATION_LOCK.md).
