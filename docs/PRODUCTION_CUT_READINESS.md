# Production-cut readiness (Phase 4 Step 12–14)

Module: `app/services/setup/production_cut_readiness.py`

## Verified (fast)

- Step 10–12 unit tests, setup e2e, one-curl certification
- `compileall` on `app`, `aethos_cli`, `scripts`

## Deferred

- Full `apply_runtime_evolution_to_truth()` cold hydration
- Full `tests/test_openclaw_*` parity suite (run in CI / nightly)

## Known slow paths

- Cold truth hydration on first API request
- Large governance timeline under load

## Posture

Orchestrator-first, advisory-first, bounded persistence, provider-routed intelligence.
