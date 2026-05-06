# AethOS agents (overview)

## Orchestration sub-agents

Registered agents (QA, security, git, etc.), Telegram `@mentions`, REST `/api/v1/agents`, and Mission Control share one registry. Full behavior and env vars:

- **[AGENT_ORCHESTRATION.md](AGENT_ORCHESTRATION.md)**

## Custom LLM agents

User-defined agents and catalog keys are separate from the orchestration registry. See **custom agents** sections in [HANDOFF_PLATFORM_OVERVIEW.md](HANDOFF_PLATFORM_OVERVIEW.md) and the web UI docs.

## Quick Telegram usage

- `/subagent create <name> <domain>` — add an orchestration agent in the current chat.
- `@<name> <instruction>` — run the sub-agent executor when orchestration is enabled.

Domain reference: `app/services/sub_agent_executor.py` dispatches by `domain` and agent name (e.g. `qa` / `security` → static security review).
