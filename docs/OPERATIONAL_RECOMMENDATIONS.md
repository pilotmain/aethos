# Operational recommendations (Phase 3 Step 10)

Bounded, **advisory** recommendations from `build_runtime_recommendations()`:

- Provider switch / fallback
- Retry strategy
- Deployment rollback
- Verification rerun
- Workspace verification
- Repair escalation
- Privacy mode hints (local-first)

All recommendations include `confidence`, `advisory: true`, and `requires_approval: true`.

API: `GET /api/v1/mission-control/runtime-recommendations`

CLI: `aethos intelligence recommendations`
