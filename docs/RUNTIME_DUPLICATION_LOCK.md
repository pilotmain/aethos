# Runtime duplication lock

**Authority:** `build_runtime_truth()` → cached truth → `apply_runtime_evolution_to_truth()`.

## Derived surfaces (must not re-fetch providers independently)

- `runtime_operator_experience`
- `runtime_enterprise_summarization`
- `enterprise_operator_experience`
- `runtime_cohesion`
- Office / Mission Control slice APIs
- `runtime_recovery_center`

## Compatibility-only duplicates

- Legacy slice builders on `mission_control_runtime` routes
- `nexa_next_state` snapshot embeds for parity

## Rule

One authoritative operational truth path. Everything else derives from hydrated truth.
