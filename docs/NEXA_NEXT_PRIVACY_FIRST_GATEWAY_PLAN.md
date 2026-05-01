# Nexa Next — Privacy-First OpenClaw-Style Multi-Agent Runtime

This document is the **product and architecture plan** for **`nexa-next`**.  
Implementation is incremental; module stubs and APIs land in the repo as phases progress.

## Repository strategy

| Repo | Role |
|------|------|
| **`nexa`** | Stable chatbot / reference / history — avoid breaking while rebuilding core. |
| **`nexa-next`** | Clean architecture: gateway runtime, privacy firewall, dynamic agents, Mission Control driven by live state. |

## Vision

- **One permanent platform identity:** Nexa (the runtime/gateway).
- **Onboarding:** user creates a **main custom agent** (personal operator); that operator **spawns dynamic mission agents** per task.
- **Differentiator vs OpenClaw-style stacks:** **Privacy-first** — PII, secrets, and sensitive content are **detected, redacted, blocked, or confirmed** before third-party APIs.

## Architecture target

```txt
Nexa Gateway
→ onboarding
→ user main agent
→ dynamic mission agents
→ event bus
→ artifacts
→ tools/plugins
→ privacy firewall
→ Mission Control
→ channels
```

Channels (**web**, **telegram**, …) enter through **`gateway.handle_message`** — no direct tool/agent bypass.

### Implemented stubs (starting point)

| Area | Location |
|------|----------|
| Gateway core | `app/services/gateway/` (`runtime.py`, `router.py`, `session.py`, `context.py`, `events.py`) |
| Privacy firewall | `app/services/privacy_firewall/` (`gateway.prepare_external_payload`, detectors, redactor, policy) |
| Mission parser | `app/services/missions/parser.py` (delegates to strict swarm parser; role-syntax missions next) |
| Onboarding | `app/services/onboarding/` (stub until `user_main_agents` table) |
| MC runtime state API | `GET /api/v1/mission-control/state` → `app/services/mission_control/nexa_next_state.py` |

## Phase checklist (summary)

- **Phase 0** — Fork `nexa-next`, clean git, README, `.env.example`, status banner. ✓ baseline in repo.
- **Phase 1** — Gateway owns sessions, routing, agents, tools, channels, privacy, MC state.
- **Phase 2** — Onboarding + `user_main_agents` (and related tables).
- **Phase 3** — Dynamic runtime agents (`app/services/runtime_agents/`).
- **Phase 4** — Mission parser (ignore Role:/Skills:/… junk; no dashboard-as-task).
- **Phase 5** — Mission graph tables (`missions`, `mission_tasks`, edges, artifacts, …).
- **Phase 6** — Event bus (`publish_event`, `list_events`, `subscribe_events`).
- **Phase 7** — Artifact system (versioned, tied to mission/task/agent).
- **Phase 8** — Worker loop (`app/services/workers/`) + dev stubs.
- **Phase 9** — Tool/plugin manifest (`workspace/config/tools.json` style).
- **Phase 10** — Privacy firewall completion (detectors, audit DB, policies).
- **Phase 11** — Single external provider gateway (`app/services/providers/`).
- **Phase 12** — Local-first / local LLM policy hooks.
- **Phase 13** — All channels via gateway only.
- **Phase 14** — Mission Control UI from **`GET /mission-control/state`** + summary (no static mocks).
- **Phase 15** — Agent-emitted **safe UI specs** (allowed components only).
- **Phase 16** — Dev mode env (firewall **stays on**).
- **Phase 17+** — Production hardening (approvals, org policy, retention).
- **Phase 18** — Test suites (parser, graph, worker, firewall, provider gateway, MC state, channel routing).
- **Phase 19** — End-to-end demo (main agent → mission → artifacts → MC + privacy panel).
- **Phase 20** — Parity/exceed OpenClaw on runtime; **exceed** on privacy and trust.

## Environment (Nexa Next–oriented)

See root **`.env.example`** — section **Nexa Next (gateway + privacy firewall)**.

## API

- **`GET /api/v1/mission-control/state`** — unified payload: execution snapshot (missions/tasks/artifacts/events) **plus** aggregate dashboard fields (overview, attention, channels, orchestration, etc.); `hours` query for trust window. Replaces the old `/mission-control/summary` route.

## Rule for Cursor / contributors

Work in **`nexa-next`** by default. Patch **`nexa`** only when explicitly maintaining the legacy app.

---

*Happy coding.*
