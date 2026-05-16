# Runtime events (Phase 2 Step 8)

Mission Control runtime events are persisted in `aethos.json` (`runtime_event_buffer`, max 2500) and published on the in-process bus for WebSockets.

## Emission

Use `app.services.mission_control.mc_runtime_events.emit_mc_runtime_event` for spec types such as:

- `agent_spawned`, `brain_selected`, `repair_started`, `repair_verified`
- `queue_pressure`, `retry_pressure`, `privacy_redaction`

Bus types are prefixed with `mission_control.` for MC consumers.

## Consumers

- `GET /api/v1/mission-control/runtime-events`
- `WS /api/v1/mission-control/runtime/ws`
- `GET /api/v1/mission-control/state` → `orchestration_runtime.runtime_events_tail`
