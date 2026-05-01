# Nexa Next — architecture boundaries

This document locks how requests flow through the system after Phase 15–17. Automated checks (`lint-imports`, `ruff`, `scripts/verify_no_direct_providers.py`, `scripts/system_integrity_check.py`, and AST tests under `tests/test_*boundaries*.py` / `tests/test_system_integrity.py`) enforce the same rules in CI.

## Provider flow

1. **Application code** (API, bot, channels, mission control, helpers) must **not** import vendor SDKs (`openai`, `anthropic`) directly. The scanner flags lines like `import openai` / `from anthropic import …` outside `app/services/providers/`.
2. **SDK construction** goes through `app/services/providers/sdk.py`: `build_openai_client` / `build_anthropic_client`. Runtime stack inspection restricts callers to:
   - `app.services.providers.*` (provider implementations),
   - `app.services.llm_service` and `app.services.response_composer` (orchestration that predates full gateway-only routing),
   - tests (`tests.*`, `pytest`, etc.).
3. **Business calls** for mission/agent execution should use **`app/services.providers.gateway.call_provider`** (`ProviderRequest`) so privacy, rate limits, and routing stay centralized.

### Phase 17 — gateway exit gate

- After `prepare_external_payload`, the merged outbound dict is wrapped in **`FrozenPayloadDict`** so it cannot be mutated before the provider runs.
- Every successful provider response is serialized and passed through **`detect_sensitive_data`** again. Secret-shaped output raises **`RuntimeError`** (fail-fast). PII-shaped output emits **`integrity.post_provider_pii_detected`**, logs **`post_provider_pii_detected`**, and fills **`STATE["integrity_alerts"]`** for Mission Control (`runtime.integrity_alert_active`, red banner).

## Plugin boundaries

- Plugins live under **`app/plugins/`**. They register tools with **`app.services.plugins.registry`** only.
- Plugins **must not** import SQLAlchemy sessions, `app.core.db`, or `app.services.providers` (see `tests/test_plugin_boundaries.py` and import-linter contract `plugins_do_not_import_providers`).

## Channel flow

- Channel adapters live under **`app/services/channels/`**.
- Inbound messages must go through **`route_inbound`** in **`app/services/channels/router.py`**, which delegates to **`NexaGateway.handle_message`**. Concrete channels (`telegram_channel`, `web_channel`, `slack_channel`) must not import **`NexaGateway`** directly (`tests/test_channel_routing.py`).
- Because optional adapters may sit outside grimp’s reachable import graph, channel isolation is primarily enforced by tests rather than import-linter.

## Privacy guarantees

- External LLM calls are gated by provider configuration, outbound gates, and Mission Control privacy indicators; strict privacy mode can force **local_stub** only.
- Mission Control events use the normalized bus schema (`type`, `timestamp`, `mission_id`, `agent`, `payload`) via `emit_runtime_event` / `publish`.

## CI pipeline

From repo root (venv active):

```bash
pytest
python scripts/verify_no_direct_providers.py
lint-imports --config importlinter.ini
python scripts/system_integrity_check.py
ruff check app/
```

`scripts/run_ci_checks.sh` runs the same sequence.
