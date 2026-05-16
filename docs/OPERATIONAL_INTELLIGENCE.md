# Operational intelligence (Phase 3 Step 1, expanded Step 9)

Lightweight, bounded insights in `build_operational_intelligence()` — no analytics warehouse.

Step 9 adds **`operational_risk`** on runtime truth (`build_operational_risk()`, `GET /mission-control/workspace-risks`): high-risk projects, deployment/repair churn, retry pressure.

Surfaces:

- queue / retry pressure
- provider instability
- repair volume
- plugin instability

Exposed on Mission Control runtime truth and `runtime-panels` as `operational_intelligence`.
