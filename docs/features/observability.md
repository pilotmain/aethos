# Observability

## Status and health

Examples:

- “Show me system status”
- “What’s the status?”
- “Health check” / “Is everything OK?”

Implementation varies by route (web, Telegram, observability intents) — see `app/services/observability/` and related API routes.

## Metrics and alerts

- Usage / cost surfaces where enabled — see [BUDGET_TRACKING.md](../BUDGET_TRACKING.md) and provider usage routes.

## What is tracked (high level)

- API requests (where instrumented)
- LLM calls and token usage (when `USE_REAL_LLM` and recorders are on)
- Command and sandbox execution outcomes
- Agent spawn and job lifecycle (mission control, dev jobs)

For security scanning and static checks, see [SECURITY_SCAN.md](../SECURITY_SCAN.md).
