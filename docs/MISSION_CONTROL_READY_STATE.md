# Mission Control ready state (Phase 4 Step 11)

After setup, Mission Control should be reachable without manual repair.

**API:** `GET /api/v1/setup/ready-state`  
**Bundled in:** `GET /api/v1/setup/status` → `mission_control_ready`

Validates: API health, bearer token, user id, `web/.env.local`, and key MC endpoints (no 500s).

**Repair:** `aethos connection repair`, `aethos setup validate`
