# Main Mission Control Natural Language Agent Creation Fix

## Problem Statement

Natural language agent creation works in Telegram and in **`POST /api/v1/web/chat`** but could fail for **`POST /api/v1/mission-control/gateway/run`** (Mission Control gateway — e.g. Mission builder / any client using `NexaGateway` directly). When the intent classifier returned **`general_chat`**, the gateway never evaluated **`prefers_registry_sub_agent`** / **`looks_like_registry_agent_creation_nl`**, so phrases like “Create a marketing agent” fell through to generic chat.

The CEO dashboard could also show **fewer agents** than **`GET /api/v1/agents/list`** / simple-CEO because it **hid terminated** orchestration agents while the list endpoint returned **all** statuses.

## Root Cause

In **`app/services/gateway/runtime.py`** (`NexaGateway.handle_full_chat`), orchestration NL spawn ran only when:

`intent in ("create_sub_agent", "create_custom_agent")`.

So **`general_chat`** + explicit NL spawn wording never entered **`try_spawn_natural_sub_agents`**, unlike **`app/services/web_chat_service.process_web_message`**, which checks **`prefers_registry_sub_agent`** earlier in the pipeline.

## Solution (implemented)

1. **Gateway** — Enter the NL spawn block when **`prefers_registry_sub_agent(raw)`** is true **or** intent is **`create_sub_agent` / `create_custom_agent`**, then spawn only when **`intent == "create_sub_agent"`** **or** **`prefers_registry_sub_agent(raw)`** (same disambiguation as before for **`create_custom_agent`**).

2. **CEO dashboard** — **`GET /api/v1/ceo/dashboard`** uses the same merged roster as **`GET /api/v1/agents/list`**, including **terminated** agents, with **`summary.terminated_agents`** for roll-ups.

## API Surface

| Path | Role |
|------|------|
| `POST /api/v1/web/chat` | Main workspace chat; already had NL spawn via **`process_web_message`**. |
| `POST /api/v1/mission-control/gateway/run` | Mission Control gateway; **fixed** to align with web chat. |
| `GET /api/v1/ceo/dashboard` | **Aligned** agent list with **`GET /api/v1/agents/list`**. |

## Verification

```bash
python -m compileall -q app
pytest tests/test_gateway_mission_control_nl_agent_creation.py tests/test_sub_agent_natural_creation.py -q
```

Restart API and Telegram bot after deploy.

## Rollback

Revert **`app/services/gateway/runtime.py`** orchestration block and **`app/api/routes/ceo_dashboard.py`** listing logic; no schema migrations.
