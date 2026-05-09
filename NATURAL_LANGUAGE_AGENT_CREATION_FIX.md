# Natural language orchestration agent creation (implemented)

## Problem

Phrases like **“Create a marketing agent”** or **“Can you create a QA agent?”** could route to
`general_chat` because:

1. **`looks_like_registry_agent_creation_nl`** rejected every message containing **`?`**, and blocked
   lines starting with **Can/Could/…** even when the user clearly asked to spawn an agent.
2. **`parse_natural_sub_agent_specs`** did not extract specs from conversational lines that do not
   match `create agent NAME DOMAIN` or `*_agent` tokens.

## Solution (this codebase)

All logic lives in **`app/services/sub_agent_natural_creation.py`** (no duplicate router stack).

1. **Detection** — `_nl_explicit_conversational_spawn_line()` recognizes polite / volitional spawn
   requests (**Can you create … agent?**, **I need a QA specialist**, **Set up a testing agent**).
   These short-circuit **`looks_like_registry_agent_creation_nl`** before the old **`?`** ban and
   **Can/Could** first-token ban (unless it is a vague multi-agent *capability* question —
   **`is_multi_agent_capability_question`** still wins).

2. **Extended verbs** — **`set up`** / **`generate`** / **`I need` / `I want` / `give me`** participate
   in the same registry NL path as **create/make/spawn**.

3. **Parsing** — **`_parse_conversational_agent_specs()`** runs first inside
   **`parse_natural_sub_agent_specs`** and produces **`(name, domain)`** for conversational lines.

4. **Intent** — **`get_intent`** / **`classify_intent_fallback`** already prioritize
   **`looks_like_registry_agent_creation_nl`** → **`create_sub_agent`**; no prompt copy change required.

## Preserved behavior

- **`create agent name domain`**, **`/subagent create`**, multi-agent roster lines, and **`*_agent`**
  handles are unchanged.
- Registry spawn still flows through **`try_spawn_natural_sub_agents`** / **`legacy_behavior_utils`**
  when orchestration is enabled.

## Tests

See **`tests/test_sub_agent_natural_creation.py`** (`test_conversational_create_agent_parsing`,
`test_prefers_registry_conversational_spawn`).
