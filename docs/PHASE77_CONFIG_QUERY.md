# Phase 77 — Config Query Intent

Users who ask **“What model are you using?”** or **“Where is my workspace?”** should get answers from live `Settings`, not action-oriented routing (host executor / next-step).

## Behavior

1. **Patterns** — `CONFIG_QUERY_PATTERNS` and `is_config_query()` in `app/services/intent_classifier.py` detect configuration questions.
2. **Intent** — `get_intent()` returns `config_query` before orchestration / registry cues so short questions are not misclassified.
3. **Handler** — `app/services/config_query.py` formats non-secret summaries:
   - LLM: `NEXA_LLM_*`, effective `ANTHROPIC_MODEL` / `OPENAI_MODEL` when keys are present.
   - Workspace: `HOST_EXECUTOR_WORK_ROOT`, `NEXA_WORKSPACE_ROOT`.
   - API keys: configured / not set only — **never** the key material.
4. **Gateway** — `NexaGateway.handle_message` answers config queries **after** credential merge and **before** sub-agent routing, operator execution, and the execution loop (`app/services/gateway/runtime.py`).
5. **Legacy chat** — `build_response` handles `config_query` for paths that still use `compose_nexa_response` / `build_response`.

## Testing

```bash
pytest tests/test_config_query.py -q
```
