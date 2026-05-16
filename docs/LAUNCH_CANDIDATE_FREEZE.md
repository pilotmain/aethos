# Launch candidate freeze

**Phase:** `phase4_step14` · **Mode:** additive-only, no breaking API changes

## Frozen

- Runtime truth architecture (`build_runtime_truth` → evolution 1–14)
- Mission Control API surface (registry in `runtime_api_capabilities.py`)
- Enterprise onboarding / setup contract (`/api/v1/setup/*`)
- Office operational model (summary-first command center)
- Orchestrator-first execution authority

## Allowed

- Certification and metrics endpoints
- Calm copy and UX polish
- Documentation and focused tests

## Not allowed

- New truth paths
- Breaking route removals
- Experimental intelligence layers
- Hidden autonomy
