# Mission Control agent visibility (Phase 59)

Natural-language **create … agents** routes to the **orchestration sub-agent registry** (same as `/subagent create`), not LLM custom agents. Detection lives in `app/services/sub_agent_natural_creation.py` (`looks_like_registry_agent_creation_nl`), coordinated with `app/services/intent_classifier.py`.

The Mission Control **Team** page loads orchestration agents via `fetchOrchestrationAgentsResolved()` in `web/lib/api/agents.ts`: it prefers `orchestration.sub_agents` from `GET /api/v1/mission-control/state`, then falls back to `GET /api/v1/agents/list`.

## Debugging scopes

With the same **`X-User-Id`** as the browser Connection settings:

```bash
curl -s "http://localhost:8010/api/v1/agents/debug/scopes" -H "X-User-Id: tg_<digits>"
```

Returns `agents_by_scope` (per `parent_chat_id` bucket) and `merged_agents` (same merge as Mission Control). Use canonical **`tg_<digits>`** in the header; see `validate_web_user_id` for aliases.

See also Phase 58 unified `DATABASE_URL` so API and Telegram bot read the same registry rows.
