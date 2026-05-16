# Automation packs (Phase 3 Step 1)

Plugins may declare `automation_pack` capability for bounded automation workflows:

- deployment
- monitoring
- workspace_maintenance
- provider_diagnostics
- repair
- project_onboarding

Packs respect plugin permissions and emit runtime events. Core orchestrator does not embed pack logic.

See `app/plugins/automation_packs.py` and **Step 10** runtime execution in `app/runtime/automation_pack_runtime.py`, `docs/AUTOMATION_RUNTIME.md`.

Operator run: `POST /api/v1/mission-control/automation-packs/{pack_id}/run`
