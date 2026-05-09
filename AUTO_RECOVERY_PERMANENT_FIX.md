# Automatic Agent Recovery for Assignments

## Problem

Orchestration sub-agents (SQLite registry, `@mention` / natural-language routing) can be marked **`terminated`** by idle cleanup. Dispatch previously treated any non-`idle` status as blocking, so users had to **Recover** in Mission Control before each assignment.

The env flag **`NEXA_ASSIGNMENT_AUTO_RECOVER`** existed in operator docs but was not wired into routing.

## Solution (implemented)

### Settings (`app/core/config.py`)

| Setting | Env var | Default |
|--------|---------|---------|
| `nexa_assignment_auto_recover` | `NEXA_ASSIGNMENT_AUTO_RECOVER` | `false` |
| `nexa_assignment_auto_recover_wait_seconds` | `NEXA_ASSIGNMENT_AUTO_RECOVER_WAIT_SECONDS` | `0` |

When **`nexa_assignment_auto_recover`** is true and the target sub-agent’s status is **`terminated`**, **`_maybe_auto_recover_terminated_for_dispatch`** in **`app/services/sub_agent_router.py`** patches the agent to **`idle`**, logs **`assignment_auto_recover`** (activity tracker + structured log), optionally sleeps up to 60s cap, then proceeds with **`AgentExecutor`**.

### Rollback

Set **`NEXA_ASSIGNMENT_AUTO_RECOVER=false`** (or omit) and restart API + bot.

## Scope note

This applies to **orchestration sub-agents** (`AgentRouter` → `AgentExecutor`), not to the separate **custom-agent SQL** pipeline (`dispatch_assignment` in `app/services/agent_team/service.py`). Custom assignments do not use the sub-agent registry `terminated` state in the same way; extend there only if CEO Dashboard shows an analogous failure mode.

## Verification

- Unit tests: `tests/test_sub_agent_router.py` (`test_route_terminated_agent_*`).
- Runtime: enable flags in `.env`, restart API (`uvicorn`) and Telegram bot.

## Example `.env`

```bash
NEXA_ASSIGNMENT_AUTO_RECOVER=true
NEXA_ASSIGNMENT_AUTO_RECOVER_WAIT_SECONDS=3
```

See **`.env.example`** for committed defaults.
