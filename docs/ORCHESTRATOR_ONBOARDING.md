# Orchestrator onboarding (Phase 4 Step 10)

`aethos setup onboarding` runs the orchestrator-first conversation (`setup_orchestrator_onboarding.py`).

Collects name, tone, goals, privacy, and provider preferences into `~/.aethos/onboarding_profile.json`.

Mission Control reads this via `GET /api/v1/mission-control/onboarding`.
