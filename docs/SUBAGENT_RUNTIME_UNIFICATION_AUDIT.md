# Subagent ↔ runtime worker unification audit (Phase 3 Step 6)

## Problem

Orchestration sub-agents (SQLite `AgentRegistry`) and runtime workers (`aethos.json` `runtime_agents`) were disconnected. AethOS could create `@agent` but answer "no visibility" on results.

## Legacy paths (kept, bridged)

| Path | Storage | Role |
|------|---------|------|
| `AgentRegistry` / `/api/v1/agents/*` | SQLite `aethos_orchestration_sub_agents` | Canonical spawn, execute, `/subagent` |
| `coordination_agents` | `aethos.json` | OpenClaw task assignment (unchanged) |
| Catalog `@dev` / `@qa` | `DEFAULT_AGENTS` | Built-in mentions (unchanged) |

## Runtime worker path (canonical visibility)

| Path | Storage | Role |
|------|---------|------|
| `runtime_agents` + `runtime_agent_handles` | `aethos.json` | Mission Control, office, truth |
| `agent_outputs` + `task_registry` | `aethos.json` | Task/output/artifact tracking |
| `agent_runtime_truth.py` | Service | Chat answers from truth |

## Bridge (Step 6)

1. **Spawn** — `AgentRegistry.spawn_agent` → `link_registry_agent_to_runtime()`
2. **Execute** — `AgentExecutor` → `create_agent_task` / `record_agent_output`
3. **Query** — `try_route_agent_status_query` / `try_agent_runtime_truth_gateway_turn` before LLM
4. **CLI** — `/subagent show|tasks|results` read runtime truth

## Deprecated / do not use for visibility

- LLM `general_chat` guessing agent state
- `active_agent_projection` catalog heuristics for orchestration agents
- Disconnected mission factory agents (`create_runtime_agents` factory) without registry link

## Migration plan

- New agents: always get runtime worker row + handle
- Existing agents: linked on next spawn or first execute
- Mission Control: `agent_visibility` on `build_runtime_truth`
