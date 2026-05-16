# AethOS documentation

## Current objective

AethOS is in a strict OpenClaw parity-first phase. The project must reproduce OpenClaw exactly as it works today before prioritizing privacy, PII filtering, local-first differentiation, cost transparency, or custom AethOS-specific architecture.

Do not introduce architectural divergence unless required to reproduce OpenClaw behavior.

Start here:

- [Project handoff](../PROJECT_HANDOFF.md)
- [OpenClaw parity audit](OPENCLAW_PARITY_AUDIT.md)
- [OpenClaw final parity audit — Phase 1 freeze & confidence lock](OPENCLAW_FINAL_PARITY_AUDIT.md)
- **Phase 1 final operational certification** (suite totals, boundedness metrics, Phase 2 readiness) — same document, *Phase 1 final operational certification (closure)* section.
- [**Phase 1 freeze declaration & Phase 2 activation boundary**](PHASE1_CERTIFICATION_CLOSURE_PHASE2_BOUNDARY.md) — normative frozen surfaces, allowed/forbidden changes, Phase 2 gate.
- [Migrating from OpenClaw](MIGRATING_FROM_OPENCLAW.md)
- [OpenClaw functional parity directive (master plan)](OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md)
- [OpenClaw functional parity implementation status](OPENCLAW_FUNCTIONAL_PARITY_STATUS.md)

## Getting started

- [Installation](installation.md)
- [Configuration](configuration.md)
- [Setup](SETUP.md)
- [Web UI / Mission Control](WEB_UI.md)

## Features

- [Agents](features/agents.md)
- [File operations](features/file-operations.md)
- [Command execution](features/command-execution.md)
- [Sandbox execution](features/sandbox.md)
- [Deployment](features/deployment.md)
- [Observability](features/observability.md)

## Development

- [Developer setup](development/setup.md)
- [Architecture](development/architecture.md)
- [Contributing](development/contributing.md)

## Legal

- [Legal overview](legal.md)
- [Trademark](legal/TRADEMARK.md)

## Business

- [Open core model](open-core.md)

## More

Operational and phase-specific guides remain as separate files in this `docs/` directory. During Phase 1, update docs whenever behavior changes and keep all claims tied to OpenClaw parity status.
