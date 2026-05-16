# Mission Control ready state

Validated endpoints (no 500s expected when API is up):

- `/api/v1/health`
- `/api/v1/setup/status`, `/api/v1/setup/ready-state`
- `/api/v1/runtime/capabilities`, `/startup`, `/readiness`, `/bootstrap`
- `/api/v1/mission-control/onboarding`, `/office`

Service: `app/services/setup/mission_control_ready_state.py`  
Tests: `tests/test_mission_control_ready_state.py`, `tests/e2e/setup/test_mission_control_ready_after_setup.py`
