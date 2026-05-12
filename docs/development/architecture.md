# Architecture

## Overview

AethOS is an **agentic operating system**: chat and web surfaces route through a **gateway** to intent classification, orchestration, tools, and optional **sandbox** or **host** execution — with policy, approvals, and observability hooks.

## Major components

| Area | Role |
| --- | --- |
| **Gateway** (`app/services/gateway/`) | NL routing, approvals, deploy/sandbox/dev NL entry points |
| **Intent** (`app/services/intent_classifier.py`, related) | Classify user text for behavior vs structured routes |
| **Agents** | Sub-agent registry, executor, templates — `app/services/sub_agent_*` |
| **Host executor** | Privileged file/command flows with policy — `app/services/host_executor*.py` |
| **Sandbox** | Plan → approve → allowlisted execution — `app/services/sandbox/` |
| **Licensing** | Optional commercial feature IDs — `app/services/licensing/` |

## Repository layout (this monorepo)

| Path | Contents |
| --- | --- |
| `app/` | FastAPI app, bots, services, models |
| `aethos_cli/` | `aethos` / `nexa` CLI entrypoints |
| `tests/` | Pytest suite |
| `web/` | Next.js Mission Control UI |
| `nexa-ext-pro/` | Optional `nexa_ext.*` extensions (packaged separately in some builds) |
| `docs/` | Documentation |

Separate **`aethos-core`** (public utilities) and **`aethos-pro`** (commercial wheels) may be published as packages; this tree remains the **full application** until a split is completed. See [open-core.md](../open-core.md).

## Request flow (simplified)

User message → channel adapter → gateway / orchestrator → handlers (LLM, tools, jobs) → response with policy and logging.

For diagrams and phased plans, see [ARCHITECTURE.md](../ARCHITECTURE.md) and [NEXA_NEXT_PRIVACY_FIRST_GATEWAY_PLAN.md](../NEXA_NEXT_PRIVACY_FIRST_GATEWAY_PLAN.md).
