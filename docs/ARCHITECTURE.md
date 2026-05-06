# Nexa Next — architecture boundaries

This document locks how requests flow through the system after Phase 15–17. Automated checks (`lint-imports`, `ruff`, `scripts/verify_no_direct_providers.py`, `scripts/system_integrity_check.py`, and AST tests under `tests/test_*boundaries*.py` / `tests/test_system_integrity.py`) enforce the same rules in CI.

## Provider flow

1. **Application code** (API, bot, channels, mission control, helpers) must **not** import vendor SDKs (`openai`, `anthropic`) directly. The scanner flags lines like `import openai` / `from anthropic import …` outside `app/services/providers/`.
2. **SDK construction** goes through `app/services/providers/sdk.py`: `build_openai_client` / `build_anthropic_client`, plus `build_async_openai_client` / `build_async_anthropic_client` for streaming. Runtime stack inspection restricts callers to:
   - `app.services.providers.*` (provider implementations),
   - `app.services.llm_service` (orchestration entrypoints),
   - `app.services.llm` (Phase 11 multi-provider backends; see [LLM_PROVIDERS.md](LLM_PROVIDERS.md)),
   - tests (`tests.*`, `pytest`, etc.).
   Structured replies in **`app.services.response_composer`** call **`primary_complete_messages`** on the Phase 11 registry (no direct vendor clients).
3. **Business calls** for mission/agent execution should use **`app/services.providers.gateway.call_provider`** (`ProviderRequest`) so privacy, rate limits, and routing stay centralized.

### Phase 17 — gateway exit gate

- After `prepare_external_payload`, the merged outbound dict is wrapped in **`FrozenPayloadDict`** so it cannot be mutated before the provider runs.
- Every successful provider response is serialized and passed through **`detect_sensitive_data`** again. Secret-shaped output raises **`RuntimeError`** (fail-fast). PII-shaped output emits **`integrity.post_provider_pii_detected`**, logs **`post_provider_pii_detected`**, and fills **`STATE["integrity_alerts"]`** for Mission Control (`runtime.integrity_alert_active`, red banner).

## Plugin boundaries

- **Phase 6 skills runtime** (YAML `skill.yaml`, process-local `PluginSkillRegistry`, optional ClawHub HTTP): see [SKILLS_SYSTEM.md](SKILLS_SYSTEM.md). This is separate from Phase 22 per-user JSON skills under `/api/v1/skills`.
- Plugins live under **`app/plugins/`**. They register tools with **`app.services.plugins.registry`** only.
- Plugins **must not** import SQLAlchemy sessions, `app.core.db`, or `app.services.providers` (see `tests/test_plugin_boundaries.py` and import-linter contract `plugins_do_not_import_providers`).

## Channel flow

- Channel adapters live under **`app/services/channels/`**.
- Inbound messages must go through **`route_inbound`** in **`app/services/channels/router.py`**, which delegates to **`NexaGateway.handle_message`**. Concrete channels (`telegram_channel`, `web_channel`, `slack_channel`) must not import **`NexaGateway`** directly (`tests/test_channel_routing.py`).
- Because optional adapters may sit outside grimp’s reachable import graph, channel isolation is primarily enforced by tests rather than import-linter.

## Privacy guarantees

- External LLM calls are gated by provider configuration, outbound gates, and Mission Control privacy indicators; strict privacy mode can force **local_stub** only.
- Mission Control events use the normalized bus schema (`type`, `timestamp`, `mission_id`, `agent`, `payload`) via `emit_runtime_event` / `publish`.

## Phase 23 — developer runtime (`app/services/dev_runtime`)

- **Persistence**: `nexa_dev_workspaces`, `nexa_dev_runs`, `nexa_dev_steps` (see `app/models/dev_runtime.py`).
- **Orchestration**: `run_dev_mission` runs a deterministic plan (no external LLM in V1): inspect (`git status`), tests (`pick_test_command` → allowlisted runner), **LocalStubCodingAgent** (no filesystem writes), tests again, summary (`prepare_pr_summary`).
- **Sandbox**: `run_dev_command` executes **only** commands in `NEXA_DEV_ALLOWED_COMMANDS`, with `cwd` locked to the workspace path and a subprocess timeout (`NEXA_DEV_COMMAND_TIMEOUT_SECONDS`).
- **Paths**: `validate_workspace_path` confines `repo_path` under configured roots (`NEXA_DEV_WORKSPACE_ROOTS` or defaults).
- **Outbound privacy**: External bodies use **`prepare_external_payload`** (`gate_outbound_dev_payload`); stored step text uses **`redact_output_for_storage`**.
- **API**: `/api/v1/dev/workspaces` and `/api/v1/dev/runs` (authenticated `X-User-Id`). Mission Control snapshot adds **`dev_workspaces`** and **`dev_runs`**.
- **Coding adapters**: `app/services/dev_runtime/coding_agents/` — only **`LocalStubCodingAgent`** is functional; Cursor/Codex/Aider/Claude modules are stubs for future wiring.
- **Gateway**: When no structured mission parses, **`maybe_dev_gateway_hint`** may return guidance if dev workspaces exist and the text looks like a dev task.

## CI pipeline

From repo root (venv active):

```bash
pytest
python scripts/verify_no_direct_providers.py
lint-imports --config importlinter.ini
python scripts/system_integrity_check.py
ruff check app/
```

`scripts/run_ci_checks.sh` runs the same sequence (and sets `NEXA_NEXT_LOCAL_SIDECAR=1` so pytest uses SQLite when Postgres from `.env` is unavailable).

Public HTTP surfaces are listed in **[docs/API_CONTRACT.md](API_CONTRACT.md)**; changes require updating that file.

## AethOS product layer (high level)

```text
┌─────────────────────────────────────────────────────────────┐
│                        AethOS core                          │
├─────────────────────────────────────────────────────────────┤
│  Gateway / router → agent registry → Mission Control      │
│  Channel adapters (Telegram, web, mobile, …)              │
│  Sub-agent executor · project / task services              │
├─────────────────────────────────────────────────────────────┤
│  Services: LLM providers · host executor · cron · PR review  │
├─────────────────────────────────────────────────────────────┤
│  Data: SQLite (default) · PostgreSQL · optional Redis        │
└─────────────────────────────────────────────────────────────┘
```

Deeper module boundaries and provider rules are in the sections above; product story: [USERGUID.md](USERGUID.md), [README.md](../README.md).
