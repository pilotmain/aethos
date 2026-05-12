<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="github-banner-dark.svg">
    <img src="github-banner-light.svg" alt="AethOS — The Agentic Operating System" width="100%">
  </picture>
</p>

<p align="center">
  <strong>The invisible layer that connects all autonomous agents</strong>
</p>

<p align="center">
  <a href="https://github.com/pilotmain/aethos/stargazers">
    <img src="https://img.shields.io/github/stars/pilotmain/aethos" alt="GitHub stars">
  </a>
  <a href="https://github.com/pilotmain/aethos/issues">
    <img src="https://img.shields.io/github/issues/pilotmain/aethos" alt="GitHub issues">
  </a>
  <a href="https://github.com/pilotmain/aethos/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="Apache 2.0">
  </a>
  <a href="https://github.com/pilotmain/aethos/blob/main/LICENSE.commercial">
    <img src="https://img.shields.io/badge/License-Commercial-red.svg" alt="Commercial License">
  </a>
  <a href="https://github.com/sponsors/pilotmain">
    <img src="https://img.shields.io/badge/Sponsor-GitHub-%23EA4AAA" alt="Sponsor on GitHub">
  </a>
</p>

# AethOS

> **Pronunciation:** “EE-thos” · **Tagline:** *The Agentic Operating System* — the invisible layer that connects autonomous agents.  
> **Repository:** [github.com/pilotmain/aethos](https://github.com/pilotmain/aethos)

**Docs:** product vision and phased plan → [docs/NEXA_NEXT_PRIVACY_FIRST_GATEWAY_PLAN.md](docs/NEXA_NEXT_PRIVACY_FIRST_GATEWAY_PLAN.md). LLM provider setup → [docs/LLM_PROVIDERS.md](docs/LLM_PROVIDERS.md).

Backward compatibility: many runtime flags still use the **`NEXA_*`** env prefix alongside **`AETHOS_*`** aliases (see `.env.example` and `app/core/config.py`).

## Open core and AethOS Pro

This repository’s **default** license is **Apache-2.0** (`LICENSE`). Some roadmap artifacts reference a future **AGPL** “core” extraction (`LICENSE.AGPL`); commercial terms for closed components are summarized in `LICENSE.commercial`.

**Not included** in the default OSS distribution (sold or licensed separately under commercial agreement):

- Advanced goal planning beyond OSS defaults  
- Packaged self-healing / enterprise extensions  
- Inter-agent negotiation “secret sauce” shipped in private builds  
- Enterprise-only surfaces (RBAC, SSO, advanced audit, etc.)

Optional **signed** license verification and feature flags: `app/services/licensing/` — set `NEXA_LICENSE_KEY` / `NEXA_LICENSE_PUBLIC_KEY_PEM` when using vendor builds. Optional **`aethos_pro`** plugins load via `aethos_core.plugin_manager` when the commercial wheel is installed.

For **commercial licensing**, contact your vendor channel (placeholder: **license@aethos.ai**). Technical overview: [docs/OPEN_CORE_COMMERCIAL_SPLIT.md](docs/OPEN_CORE_COMMERCIAL_SPLIT.md).

---

## One-command install

**Recommended (no custom domain yet):** clone + venv + dependencies + `aethos setup` wizard:

```bash
curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/install.sh | bash
```

**Same flow, explicit script path:**

```bash
curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/scripts/install_aethos.sh | bash
```

Optional **Pro license string** (writes into your session for the wizard / `.env`; still needs a vendor **signed** key flow when you use commercial builds):

```bash
curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/install.sh | bash -s -- --license 'YOUR_KEY'
```

Then: `aethos setup` → `aethos serve` (if the wizard did not already run). Deeper bootstrap: [docs/SETUP.md](docs/SETUP.md). Short guides: [docs/API.md](docs/API.md) · [docs/AGENTS.md](docs/AGENTS.md) · [docs/SECURITY_SCAN.md](docs/SECURITY_SCAN.md).

**Legacy / alternate** Docker-first bootstrap (different code path): [scripts/install.sh](scripts/install.sh) and `python scripts/nexa_bootstrap.py` — see [docs/SETUP.md](docs/SETUP.md).

### Optional three-package / PyPI hooks (maintainers)

Today’s **default** installer still **clones this monorepo** and runs `pip install -r requirements.txt` + `pip install -e .` — that is the supported OSS path and is **not** replaced until published wheels cover the same runtime.

When **`aethos-core`** is on PyPI and **`aethos-pro`** is on a **private index** (Google Artifact Registry, AWS CodeArtifact, etc.), you can layer wheels **without** forking the script:

| Environment variable | Purpose |
| ---------------------- | ------- |
| `AETHOS_PYPI_INSTALL_CORE` | pip spec for the public core wheel, e.g. `aethos-core` or `aethos-core==0.1.0` |
| `AETHOS_PYPI_INSTALL_PRO` | pip spec for Pro, e.g. `aethos-pro` |
| `AETHOS_PRO_EXTRA_INDEX_URL` | Required for Pro: passed to `pip install … --extra-index-url …` |

Example (non-interactive, after you have real package names and index URL):

```bash
export AETHOS_PYPI_INSTALL_CORE='aethos-core'
export AETHOS_PYPI_INSTALL_PRO='aethos-pro'
export AETHOS_PRO_EXTRA_INDEX_URL='https://YOUR_INDEX/simple/'
curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/install.sh | bash
```

`--license` / `NEXA_LICENSE_KEY` still feed the **wizard and runtime** licensing hooks; **pip** to a private index usually needs **its own** auth (token in the index URL or `PIP_INDEX_URL` / netrc) — configure that in your CI or operator docs.

**Maintainer checklist (not automated here):** publish `aethos-core` to PyPI → stand up private index for `aethos-pro` → smoke-test the three env vars above → optionally point **`https://aethos.ai/install`** at the raw GitHub `install.sh` URL via DNS / CDN redirect.

## What is AethOS?

**AethOS** is an **agentic operating system**: it helps you think, plan, research, create documents, manage projects, and **execute** work through chat, a **web** workspace, **Telegram**, and automation. It **creates task-focused agents dynamically** when work needs them. It is a **platform**: custom agents, dedicated Dev and Ops surfaces, public web research and **web search**, **BYOK** multi-tenant key handling, a **usage / cost** dashboard, and durable **memory**—not a single “chat only” app.

AethOS is **not** just a chatbot. It is an **execution layer** that uses **LLMs** when they add the most value, **tools** when a deterministic or external step is better, and **approval gates** when an action is risky (jobs, reviews, rollouts, privileged commands). That keeps the system honest, inspectable, and controllable as scale grows.

**New here?** Plain-language overview and first workflow story: [docs/USERGUID.md](docs/USERGUID.md) · [docs/WORKFLOW_DEMO.md](docs/WORKFLOW_DEMO.md).

**Maintainers and agents:** internal handoff packs (planning slices, Cursor guardrails, week notes, phase audits) live under **`~/.aethos/docs/handoffs/`** on your machine — they are **not** shipped in this repository. For the picture of the codebase in-repo, start with [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/ROADMAP.md](docs/ROADMAP.md). Day-to-day workflow: [docs/DEVELOPMENT_HANDOFF.md](docs/DEVELOPMENT_HANDOFF.md).

## Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ AethOS Core                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│  │ Gateway      │    │ Agent        │    │ Mission      │                 │
│  │ Router       │◄──►│ Registry     │◄──►│ Control      │                 │
│  └──────────────┘    └──────────────┘    └──────────────┘                 │
│         │                   │                   │                         │
│         ▼                   ▼                   ▼                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│  │ Channel      │    │ Agent        │    │ Project      │                 │
│  │ Adapters     │    │ Executor     │    │ Manager      │                 │
│  │              │    │              │    │              │                 │
│  │ • Telegram   │    │ • QA Agent   │    │ • Projects   │                 │
│  │ • Slack      │    │ • Security   │    │ • Tasks      │                 │
│  │ • Web UI     │    │ • CEO Agent  │    │ • Kanban     │                 │
│  │ • Mobile     │    │ • Marketing  │    │ • Budget     │                 │
│  └──────────────┘    └──────────────┘    └──────────────┘                 │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ Services Layer                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│  │ LLM          │    │ Browser      │    │ Cron         │                 │
│  │ Providers    │    │ Automation   │    │ Scheduler    │                 │
│  └──────────────┘    └──────────────┘    └──────────────┘                 │
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│  │ Social       │    │ PR           │    │ Memory       │                 │
│  │ Automation   │    │ Reviews      │    │ Store        │                 │
│  └──────────────┘    └──────────────┘    └──────────────┘                 │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ Data Layer                                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│  │ SQLite       │    │ PostgreSQL   │    │ Redis        │                 │
│  │ (default)    │    │ (optional)   │    │ (optional)   │                 │
│  └──────────────┘    └──────────────┘    └──────────────┘                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Docs

- **Frozen public HTTP API** → [docs/API_CONTRACT.md](docs/API_CONTRACT.md) — paths and change rule for contributors
- **Architecture** → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — how AethOS is built (Arcturus)
- **Multi-provider LLM** → [docs/LLM_PROVIDERS.md](docs/LLM_PROVIDERS.md) — backends, diagram, env checklist (DeepSeek, Ollama, fallbacks)
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

**From the project root** — create or refresh `.env`, Python venv, optional Docker, and health checks using the steps in [docs/SETUP.md](docs/SETUP.md) (bootstrap script entry points are documented there).

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
| [docs/LLM_PROVIDERS.md](docs/LLM_PROVIDERS.md) | **Multi-provider LLM:** architecture diagram, env checklist (DeepSeek, Ollama, fallbacks) |
| [docs/CHANNEL_GATEWAY.md](docs/CHANNEL_GATEWAY.md) | **Design:** multi-channel gateway (Slack, WhatsApp, email…) without weakening governance |
| [docs/CHANNEL_GATEWAY_EXECUTION.md](docs/CHANNEL_GATEWAY_EXECUTION.md) | **Execution plan:** phased adapter extract, router, identity, Slack/email, tests |
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

This is an **actively evolving** system: production hardening, scaling, and compliance are deployment-specific—see [docs/DEVELOPMENT_HANDOFF.md](docs/DEVELOPMENT_HANDOFF.md) and the developer notes under `docs/` for how we ship and verify.

## License

AethOS is **dual-licensed**:

- **Open source:** [Apache License 2.0](LICENSE)
- **Commercial:** Pro features, enterprise deployments, and support — see [LICENSE.commercial](LICENSE.commercial)

| Feature | Apache 2.0 (open source) | Commercial license |
| --- | --- | --- |
| Core agent functionality | Yes | Yes |
| File operations | Yes | Yes |
| Command execution | Yes | Yes |
| Sandbox execution | Yes | Yes |
| Pro features (GoalPlanner, SelfHealingEngine, packaged Pro negotiation, etc.) | No | Yes |
| Enterprise-oriented features (SSO, advanced audit, compliance packages) | No | Yes |
| Priority support / SLA | No | Yes (when purchased) |

Commercial inquiries: **[license@aethos.ai](mailto:license@aethos.ai)**
