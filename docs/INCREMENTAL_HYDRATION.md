# Incremental hydration

`build_runtime_truth()` delegates to `hydrate_runtime_truth_incremental()`, which builds and merges slices:

1. **core** — health, agents, deployments, providers, events (bounded).
2. **workers** — office view, runtime workers, agent visibility.
3. **intelligence** — operational intelligence engine, recommendations.
4. **workspace** — workspace intelligence, risk, continuity, research chains.
5. **worker_memory** — deliverables, continuations (bounded).
6. **governance** — governance audit, automation packs.
7. **derived** — confidence, readable summaries, enterprise panels, cohesion bundle.

Slice cache keys live under `mc_runtime_slice_cache` in runtime state. Invalidate with `invalidate_slice_cache(user_id, slice_name?)`.

See also `docs/RUNTIME_CACHE_ARCHITECTURE.md` and `docs/MISSION_CONTROL_RESPONSIVENESS.md`.
