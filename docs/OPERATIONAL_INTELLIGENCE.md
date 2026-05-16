# Operational intelligence (Phase 3 Step 1, expanded Step 9)

Lightweight, bounded insights in `build_operational_intelligence()` — no analytics warehouse.

Step 9 adds **`operational_risk`** on runtime truth (`build_operational_risk()`, `GET /mission-control/workspace-risks`): high-risk projects, deployment/repair churn, retry pressure.

Step 10 adds **`build_operational_intelligence_engine()`** — signals, proactive suggestions, `runtime_insights`, `enterprise_operational_state`, automation pack runtime, and **`runtime_recommendations`** (advisory, confidence-scored). APIs: `/operational-intelligence`, `/runtime-insights`, `/runtime-recommendations`, `/enterprise-runtime`. See `docs/OPERATIONAL_RECOMMENDATIONS.md`.

Surfaces:

- queue / retry pressure
- provider instability
- repair volume
- plugin instability

Exposed on Mission Control runtime truth and `runtime-panels` as `operational_intelligence`.
