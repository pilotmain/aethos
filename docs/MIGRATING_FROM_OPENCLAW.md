# Migrating from OpenClaw to AethOS

This guide is now governed by the Phase 1 **OpenClaw parity** objective:

> AethOS must reproduce OpenClaw exactly as it works today before privacy, PII filtering, local-first differentiation, cost transparency, or custom AethOS-specific improvements become primary work.

Do not introduce architectural divergence unless required to reproduce OpenClaw behavior.

Use this guide to map an OpenClaw-style setup into AethOS while preserving behavior first. The **master implementation plan** (CLI matrix, priorities, test modules) is [OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md](OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md).

## Migration rule

Do not treat differences as product advantages during Phase 1. Treat them as gaps unless they are explicitly required to reproduce OpenClaw behavior.

## What to map first

1. Chat/operator channels used in the current OpenClaw setup.
2. Agent creation, delegation, and orchestration workflows.
3. File, shell, browser, and deployment tool flows.
4. Memory/context expectations across sessions.
5. Provider/model routing and fallback behavior.
6. Mission Control/operator UI flows.
7. Autonomy, scheduler, and long-running agent behavior.

## Setup checklist

1. Copy `.env.example` to `.env`.
2. Set `NEXA_SECRET_KEY`, owner IDs, web token, and provider keys.
3. Align API port, web API base, and CORS origins.
4. Configure the same channels used in the OpenClaw reference setup.
5. Configure workspace roots and command execution gates for the parity scenario.
6. Enable realistic LLM/provider routing for parity testing.
7. Run schema initialization.
8. Start API, web, and exactly the required channel workers.
9. Run parity tests and record gaps in `docs/OPENCLAW_PARITY_AUDIT.md`.

## Phase 1 behavior expectations

A migration is successful only if the reproduced workflow behaves like the OpenClaw reference workflow from the operator's perspective.

Examples:

- Same kind of agent response and delegation behavior.
- Same mission/run lifecycle shape.
- Same file/tool execution expectations.
- Same deployment workflow expectations.
- Same memory/context continuity expectations.
- Same channel routing expectations.

## Phase 2 differences

AethOS may later add or strengthen:

- privacy firewall behavior;
- PII filtering;
- strict/local-first routing;
- cost transparency;
- stronger sandboxing;
- richer governance and audit controls.

During Phase 1, these must not prevent or reshape the OpenClaw-compatible path unless explicitly required for parity.

## Honest limitations

If a feature does not yet match OpenClaw, mark it as a parity gap in `docs/OPENCLAW_PARITY_AUDIT.md`. Do not hide missing behavior behind branding, roadmap language, or claims of intentional differentiation.
