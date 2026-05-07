# Phase 66: Natural-language sub-agent invocation (no `@` required)

## Summary

When `NEXA_AGENT_ORCHESTRATION_ENABLED=true`, the gateway already calls `try_sub_agent_gateway_turn` **before** operator execution, execution loop, missions, and full chat (`NexaGateway.handle_message` in `app/services/gateway/runtime.py`). Phase 66 extends **that same early hop** so phrases like `ask security_agent to scan /path` route to a **registered** sub-agent for the current chat scope, not only leading `@name` messages.

## Safety (does not hijack normal chat)

- NL patterns only produce a route when `AgentRegistry.resolve_agent_by_name(...)` finds a **real** agent in the chat’s `parent_chat_id` (same scope as `@` routing).
- Unknown names → no match → `handled: false` → existing Mission Control / chat flow unchanged.
- Lines starting with `/` are ignored for NL extraction (slash commands unchanged).

## Routing order (within orchestration)

1. **Leading `@mention`** — unchanged (case-sensitive name as typed after `@`, same as before).
2. **NL extraction** — when `NEXA_NATURAL_AGENT_INVOCATION=true` (default).
3. Otherwise gateway continues (operator, execution loop, structured routes, `handle_full_chat`, including NL **agent creation** via intent).

Agent **creation** NL (`create_sub_agent` / `try_spawn_natural_sub_agents`) stays in `handle_full_chat`; it is not displaced by Phase 66.

## Code locations

| Piece | File |
|--------|------|
| NL patterns + `@` dispatch | `app/services/sub_agent_router.py` (`try_extract_natural_language_sub_agent`, `AgentRouter.route`, `_dispatch_known_sub_agent`) |
| Case-insensitive name resolve | `app/services/sub_agent_registry.py` (`resolve_agent_by_name`) |
| Settings flag | `app/core/config.py` (`nexa_natural_agent_invocation`) |
| Env template | `.env.example` (`NEXA_NATURAL_AGENT_INVOCATION`) |
| Tests | `tests/test_sub_agent_router.py` |

## Supported NL shapes (examples)

| User text | Instruction passed to executor |
|-----------|----------------------------------|
| `ask my_agent to run pytest` | `run pytest` |
| `tell research_agent to summarize the doc` | `summarize the doc` |
| `get ops_agent to monitor /var/log` | `monitor /var/log` |
| `have content_creator write a post` | `write a post` |
| `make test_qa run pytest` | `run pytest` |
| `what is research_agent doing` | `status` |
| `security_agent status` | `status` (prefix form; longest registered name wins) |

## Configuration

```bash
# Default in Settings: true. Set false to require @ only.
NEXA_NATURAL_AGENT_INVOCATION=true
```

## Verification

```bash
cd ~/aethos
source .venv/bin/activate
python -m compileall -q app
pytest tests/test_sub_agent_router.py -q
```

Restart API and Telegram bot so `Settings` and router code reload.

## Cursor one-liner

Apply Phase 66: NL sub-agent routing in `app/services/sub_agent_router.py` with registry-only name matches; add `resolve_agent_by_name` and `nexa_natural_agent_invocation` / `NEXA_NATURAL_AGENT_INVOCATION`; tests in `tests/test_sub_agent_router.py`.
