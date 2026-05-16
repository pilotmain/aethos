# Architecture simplification (Phase 3 Step 3)

```text
runtime state (aethos.json)
        ↓
build_runtime_truth()  ← single authoritative builder
        ↓
runtime_truth_cache (5s)
        ↓
┌───────────────────┬────────────────────┬─────────────────┐
│ Mission Control   │ Office operational │ Differentiators │
│ panels / APIs     │ view               │ summary         │
└───────────────────┴────────────────────┴─────────────────┘
```

## Principles

1. **One truth path** — no parallel MC builders
2. **Orchestrator is AethOS** — all other agents are ephemeral workers
3. **Signal over noise** — aggregated, aged, severity-prioritized events
4. **Bounded state** — buffers, caches, discipline metrics
5. **API-first UI** — Mission Control never uses static operational data
