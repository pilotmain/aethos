# Mission Control agent unification (implemented)

## Problem

Mission Control and `GET /api/v1/agents/list` merged agents only by **registry scope**
(`web:{user}:session`, `telegram:{id}`, etc.). Agents created in **Telegram group chats**
use `parent_chat_id = telegram:{group_chat_id}`, which is **not** included in the merged
scopes for `tg_<digits>` API users—so those agents disappeared from the dashboard even though
the API returned agents from web spawn paths.

## Solution (this repo)

1. **Stamp ownership** — On spawn, set `metadata["app_user_id"]` to the canonical API user id
   (`X-User-Id`). Implemented via `owner_app_user_id` on
   `AgentRegistry.spawn_agent` (`ORCH_OWNER_APP_USER_ID_META_KEY`).

2. **Unified listing** — `AgentRegistry.list_agents_for_app_user(app_user_id)` returns:
   - agents matched by existing `list_agents_merged(orchestration_registry_scopes(app_user_id)))`, **plus**
   - any non-terminated agent whose `metadata["app_user_id"]` equals `app_user_id`.

3. **API alignment** — `/api/v1/agents/list`, `/api/v1/ceo/dashboard`, Mission Control read model,
   agent CRUD health routes, and Telegram `/subagent` flows use this unified list where appropriate.

4. **Explicit endpoint** — `GET /api/v1/mission/agents` returns the same roster with a `source`
   hint (`web` vs `telegram` vs `other`) from `parent_chat_id`.

## Existing agents without metadata

Agents created **before** this change may lack `app_user_id` in metadata. They remain visible
only if their `parent_chat_id` already falls under merged scopes. Re-create or patch metadata if
needed.

## Testing

- Spawn via Mission Control / API → appears with `source: web`.
- Spawn via Telegram `/subagent create` → stamped with owner; appears with `source: telegram`
  even for group chats.
