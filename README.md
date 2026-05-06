# AethOS (repository: `nexa-next`)

> **Pronunciation:** “EE-thos” · **Tagline:** *The Agentic Operating System* · From **Aether** (the classical element) + **OS** — the invisible layer that connects autonomous agents.
>
> **This GitHub repository remains [`nexa-next`](https://github.com/pilotmain/nexa-next)** until the remote is renamed; clone URLs and CI may still say `nexa-next`. Product branding in the app, CLI, and docs is **AethOS**.

**Docs:** product vision and phased plan → [docs/NEXA_NEXT_PRIVACY_FIRST_GATEWAY_PLAN.md](docs/NEXA_NEXT_PRIVACY_FIRST_GATEWAY_PLAN.md). **Phase 36 rebrand playbook:** [docs/PHASE_36_REBRAND_AETHOS.md](docs/PHASE_36_REBRAND_AETHOS.md).

---

## One-command install

```bash
curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/scripts/install_aethos.sh | bash
```

Then: `aethos setup` → `aethos serve`. Deeper bootstrap: [docs/SETUP.md](docs/SETUP.md). Short guides: [docs/API.md](docs/API.md) · [docs/AGENTS.md](docs/AGENTS.md) · [docs/SECURITY_SCAN.md](docs/SECURITY_SCAN.md).

# AethOS

**AethOS** is an **agentic operating system**: it helps you think, plan, research, create documents, manage projects, and **execute** work through chat, a **web** workspace, **Telegram**, and automation. It **creates task-focused agents dynamically** when work needs them. It is a **platform**: custom agents, dedicated Dev and Ops surfaces, public web research and **web search**, **BYOK** multi-tenant key handling, a **usage / cost** dashboard, and durable **memory**—not a single “chat only” app.

AethOS is **not** just a chatbot. It is an **execution layer** that uses **LLMs** when they add the most value, **tools** when a deterministic or external step is better, and **approval gates** when an action is risky (jobs, reviews, rollouts, privileged commands). That keeps the system honest, inspectable, and controllable as scale grows.

**New here?** Plain-language overview and first workflow story: [docs/USERGUID.md](docs/USERGUID.md) · [docs/WORKFLOW_DEMO.md](docs/WORKFLOW_DEMO.md).

**Maintainers and agents:** full **platform overview** (for the next agent or planner): [docs/HANDOFF_PLATFORM_OVERVIEW.md](docs/HANDOFF_PLATFORM_OVERVIEW.md). **Architecture** and **roadmap:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/ROADMAP.md](docs/ROADMAP.md). **Implementation guardrails:** [docs/CURSOR_HANDOFF.md](docs/CURSOR_HANDOFF.md).

## Docs

- **Frozen public HTTP API** → [docs/API_CONTRACT.md](docs/API_CONTRACT.md) — paths and change rule for contributors
- **Platform handoff (agents / planning)** → [docs/HANDOFF_PLATFORM_OVERVIEW.md](docs/HANDOFF_PLATFORM_OVERVIEW.md) — full-picture map and where to go deeper
- **Architecture** → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — how AethOS is built (Arcturus)
- **Phase 11 (multi-provider LLM)** → [docs/PHASE_11_LLM_PROVIDERS.md](docs/PHASE_11_LLM_PROVIDERS.md) — planned DeepSeek/Ollama/OpenRouter layer, diagram, env vars
- **Roadmap** → [docs/ROADMAP.md](docs/ROADMAP.md) — where AethOS is going (phases)
- **Channel Gateway (design)** → [docs/CHANNEL_GATEWAY.md](docs/CHANNEL_GATEWAY.md) — Slack, email, WhatsApp, etc. on a shared adapter layer
- **Channel Gateway (execution plan)** → [docs/CHANNEL_GATEWAY_EXECUTION.md](docs/CHANNEL_GATEWAY_EXECUTION.md) — phases, ground rules, effort
- **User guide** → [docs/USERGUID.md](docs/USERGUID.md) — product story (non-technical)
- **Workflow demo** → [docs/WORKFLOW_DEMO.md](docs/WORKFLOW_DEMO.md) — idea → execution walkthrough

## Features (what is included)

- **Web app** — Next.js workspace, chat, document export, and co-pilot flows; see [docs/WEB_UI.md](docs/WEB_UI.md)
- **Telegram bot** — on-the-go capture, dev job queue, and role-aware access
- **Custom agents** — pluggable, behavior-driven; evolve through chat
- **Dev agent** — repo work in a **review** loop (Cursor/Codex-style handoffs); see [docs/DEV_JOBS.md](docs/DEV_JOBS.md)
- **Ops agent** — deployment- and environment-aware help (e.g. Railway, local docker); see the orchestrator and ops services in `app/services/ops/`
- **Public web research** — read and cite public pages with clear provenance
- **Web search** — configured providers (e.g. Brave, Tavily) for live discovery
- **Document generation** — generate artifacts from the assistant (e.g. PDF, Word) via API and UI
- **BYOK** — per-user OpenAI / Anthropic keys encrypted at rest; [docs/MULTI_USER.md](docs/MULTI_USER.md)
- **Usage and cost** — model usage and cost visibility in the system (dashboard and/or bot surfaces, depending on deployment)
- **Memory and “soul”** — long-lived preferences, patterns, and owner-tunable personality files
- **Multi-user roles** — owner / trusted / default Telegram roles, `/access` introspection, block lists

Core planning and execution: brain dumps, task/plan generation, check-ins, follow-up scheduling, and a **FastAPI** backend (SQLite or Postgres; Docker optional).

## Quick start

**One-line install** — clones the repo, creates venv and `.env`, optional API prompts, then starts Docker (when available) or API + web on the host. Requires **Git** and **Python 3.10+**.

```bash
curl -fsSL https://pilotmain.com/install.sh | bash
```

Already have the repo? From the project root:

```bash
./scripts/install.sh --no-clone
```

Options and environment variables: [docs/SETUP.md](docs/SETUP.md#one-line-install).

---

**From the project root** (creates / fills `.env`, venv, optional Docker, health check):

```bash
python scripts/nexa_bootstrap.py
```

Then: open Telegram, `/start`, and (to use your own model keys) `/key set openai` or set keys in `.env` and `USE_REAL_LLM=true`.

**Deeper setup** (Docker, Compose Watch, SQLite, dev executor, “always on”): [docs/SETUP.md](docs/SETUP.md)  
**Operator, launchd, autonomy:** [docs/OPERATIONS.md](docs/OPERATIONS.md)  
**Dev job pipeline and phone → machine loop:** [docs/DEV_JOBS.md](docs/DEV_JOBS.md) and [docs/DEV_JOB_FLOW.md](docs/DEV_JOB_FLOW.md)

## Using AethOS

- **Web** — with `run_everything.sh` (or your Node dev command), the UI is usually at [http://localhost:3000](http://localhost:3000) (API at [http://localhost:8010](http://localhost:8010)). [docs/WEB_UI.md](docs/WEB_UI.md)  
- **Telegram** — `/start`, `/help`, plan commands (`/today`, `/overwhelmed`), dev/Ops and agent invocations; full command list in-app via `/help`.  
- **Multi-user and keys** — [docs/MULTI_USER.md](docs/MULTI_USER.md)  
- **Research and documents** — use the chat surfaces; exports appear where your deployment exposes document and artifact UIs.  

## More documentation

| Doc | What |
| --- | ---- |
| [docs/HANDOFF_PLATFORM_OVERVIEW.md](docs/HANDOFF_PLATFORM_OVERVIEW.md) | **Start here for agents:** whole-product map, stack, modules, roadmap hooks, doc index |
| [docs/PHASE_11_LLM_PROVIDERS.md](docs/PHASE_11_LLM_PROVIDERS.md) | **Phase 11 plan:** multi-provider LLM, architecture diagram, env checklist (DeepSeek, Ollama, fallbacks) |
| [docs/CHANNEL_GATEWAY.md](docs/CHANNEL_GATEWAY.md) | **Design:** multi-channel gateway (Slack, WhatsApp, email…) without weakening governance |
| [docs/CHANNEL_GATEWAY_EXECUTION.md](docs/CHANNEL_GATEWAY_EXECUTION.md) | **Execution plan:** phased adapter extract, router, identity, Slack/email, tests |
| [docs/HANDOFF_RECENT_WORK.md](docs/HANDOFF_RECENT_WORK.md) | Narrow slice: recent install path, web session delete, pilotmain.com redirect notes |
| [docs/SETUP.md](docs/SETUP.md) | Bootstrap, local dev, Docker, LLM options, test flow, API surface |
| [docs/WEB_UI.md](docs/WEB_UI.md) | Web app behavior and local URLs |
| [docs/MULTI_USER.md](docs/MULTI_USER.md) | BYOK, roles, `/access` |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Operator loop, `run_everything` extras, host dev executor, supervision |
| [docs/DEV_JOBS.md](docs/DEV_JOBS.md) | Autonomous dev jobs, approvals, always-on machine |
| [docs/DEV_JOB_FLOW.md](docs/DEV_JOB_FLOW.md) | End-to-end job flow and checks |
| [docs/WORKSPACE_AND_PERMISSIONS.md](docs/WORKSPACE_AND_PERMISSIONS.md) | Workspace strict mode, host permissions, Docker vs grants |

## Product direction (near term)

- **Custom agents** — deeper configuration and management from chat  
- **Web UI** — more first-class product surface, parity and polish with Telegram where it matters  
- **Document export** — smoother formats and handoff to other tools  
- **Web research / search** — more transparency on sources, limits, and retries  
- **Cost and decision transparency** — make model choice and tool use legible in the product  
- **Simpler setup** — one-path onboarding for self-host and small teams  
- **Audio input** (later) — hands-free capture aligned with the same memory and plan pipeline

---

This is an **actively evolving** system: production hardening, scaling, and compliance are deployment-specific—see `docs/CURSOR_HANDOFF.md` and the developer notes under `docs/` for how we ship and verify.
