# Nexa — platform overview for agents and planners

**Purpose:** Give the **next engineer or agent** a single **full-picture** view of what Nexa is, how the repo is organized, what’s implemented, and where to look for depth—so you can **prioritize recommendations** and next work. This doc **summarizes**; it does not replace the specialized guides linked below.

**How to use it**

- Skim **§1–3** for product and stack, **§4–6** for architecture map, **§7** for roadmap fit, **§8** for “where to go deeper.”
- For a **short slice** of work done in a recent period (install script, web session delete, `pilotmain.com` redirect notes), see [HANDOFF_RECENT_WORK.md](HANDOFF_RECENT_WORK.md).
- For **day-to-day dev** (run, test, agent jobs), see [DEVELOPMENT_HANDOFF.md](DEVELOPMENT_HANDOFF.md) and [CURSOR_HANDOFF.md](CURSOR_HANDOFF.md).

---

## 1. What Nexa is (product)

- **Not** a single-purpose chatbot. Nexa is an **AI execution system** that creates task-focused agents dynamically when work needs them: think, plan, research, create documents, manage projects, and **execute** work through **conversation**.
- **Surfaces:** **Web** (Next.js workspace) and **Telegram** (commands, capture, dev/Ops flows) on the same **FastAPI** backend.
- **Positioning:** An **execution layer**—LLMs when they add value, **tools** when deterministic steps are better, **approval gates** for risky or irreversible actions (jobs, host tools, network egress, etc.).
- **Platform traits:** Custom agents, built-in specialists (`@dev`, `@ops`, research/marketing/strategy-style paths), **BYOK** keys, usage/cost visibility, **memory** and conversation state, **durable jobs** (especially dev agent work), and **governance** (roles, permissions, safety policy, audit / trust signals).
- **Core loop (conceptual):** conversation → **decision** (routing, risk) → **execution** (tools, jobs) → **outcome** + **observability** (decision summary, system events, trust/usage where enabled).

---

## 2. Technical stack

| Layer | Technology / notes |
|--------|-------------------|
| API | **FastAPI** (`app/main.py`), OpenAPI at `/docs` when running |
| API prefix | Configurable; default **`/api/v1`** (`app/core/config.py`) |
| Web UI | **Next.js** in `web/`; main shell **WorkspaceApp** |
| Mobile / async | **Telegram** long-polling bot (`app/bot/telegram_bot.py`) |
| Database | **SQLite** by default; **Postgres** in Docker (`docker-compose.yml`, `env.docker.example`) |
| Schema | **SQLAlchemy** models; `ensure_schema()` on API startup (`app/core/db.py`) |
| Background work | **APScheduler** in API lifespan: check-ins + **operator/supervisor** loop (`app/workers/`) |
| LLM | Anthropic / OpenAI (and config); **safe** gateway and policy layers in `app/services/` |
| Dev automation | **Dev jobs**, dev orchestrator package, optional **host-side** dev executor scripts |
| Ops | Provider-style connectors under **`app/services/ops/`** |

---

## 3. Repository layout (top level)

| Path | Role |
|------|------|
| `app/` | Backend: API routes, models, services, bot, workers |
| `web/` | Next.js frontend |
| `tests/` | Pytest suite |
| `scripts/` | Bootstrap, installers, executors, tooling |
| `docs/` | Architecture, roadmap, setup, operations, web UI, permissions, handoffs |
| `docker-compose.yml` | Postgres + API + bot stack |
| `run_everything.sh` | One script: **Docker** (Postgres or SQLite compose: API + bot + scheduler/operator in-process) + optional **Next.js** (:3000) + optional **host dev executor**; or **`native`** (host `.venv` + `scripts/start_operator_stack.sh` without Docker). |
| `requirements.txt` | Python dependencies |

---

## 4. Backend API surface (routers)

Mounted from `app/main.py` (prefix `/api/v1` unless noted):

| Router module | Typical concerns |
|---------------|------------------|
| `health` | Health checks |
| `auth` | Auth-related API |
| `tasks`, `plans`, `checkins`, `dumps` | Tasks, planning, brain dumps, check-ins |
| `memory` | Memory API |
| `jobs` | Agent / dev jobs |
| `dashboard` | Dashboard |
| `web` | **Browser web UI**: sessions, chat, workspace, usage, keys, system status, **DELETE sessions**, etc. |
| `permissions` | Permission requests / approvals used by web + flows |
| `trust` | Trust / audit style read APIs where implemented |
| `internal` | Internal integration endpoints |

**Security:** Web routes expect identity headers (e.g. **`X-User-Id`**) and optional bearer token per deployment (`app/core/security.py`, settings).

---

## 5. Major service domains (where logic lives)

Clustered by theme — browse `app/services/` for the full list (50+ modules).

| Domain | Examples (indicative paths) |
|--------|------------------------------|
| **Orchestration & chat** | `behavior_engine.py`, `agent_orchestrator.py`, `intent_classifier.py`, `web_chat_service.py`, `response_composer.py` |
| **Agents** | `agent_catalog.py`, `custom_agents.py`, `custom_agent_intent.py`, `agent_job_service.py`, `mention_control.py` |
| **Dev pipeline** | `dev_orchestrator/`, `dev_task_service.py`, `dev_tools/`, `cursor_dev_handoff.py`, policies and guards |
| **Ops** | `ops/` package |
| **Conversation & sessions** | `conversation_context_service.py` (per-user/session state; web session delete/clear) |
| **Permissions & access** | `access_permissions.py`, `permission_request_flow.py`, `permission_resume_execution.py`, `permission_reply_guard.py`, workspace registry helpers |
| **Safety & enforcement** | `nexa_safety_policy.py`, `enforcement_pipeline.py`, `nexa_policy_guard.py`, `content_provenance.py`, `secret_egress_gate.py`, `outbound_request_gate.py`, `safe_http_client.py`, etc. |
| **Host / local execution** | `host_executor.py`, `host_executor_chat.py`, `host_executor_visibility.py` |
| **Tools** | Web fetch/search, document generation, browser preview (as configured) |
| **Memory & learning** | `memory_service.py`, learning events, dumps |
| **Observability** | `decision_summary.py`, usage recording, `trust_audit_*`, audit service |
| **Product** | `release_updates`, onboarding, Telegram copy |
| **Bootstrap** | `nexa_bootstrap.py` (one-command env + venv + optional Docker) |

**Bot:** `app/bot/telegram_bot.py` is large; it routes commands, permissions, dev flows, and links to the same services as the API.

**Workers:** `app/workers/followup_worker.py` (check-ins), `operator_supervisor.py` (operator cycle, job advancement when enabled).

---

## 6. Web and Telegram UX (high level)

- **Web:** Multi-session chat, jobs panel, system status, access/permissions, trust activity (where built), cost/usage, document flows—see [WEB_UI.md](WEB_UI.md).
- **Telegram:** Role-aware commands, dev job queue, **Ops**/**Dev** style invocations, `/access`, plan commands—see bot help and [MULTI_USER.md](MULTI_USER.md).
- **Shared contract:** Decisions and “system” lines are designed to be **legible** (agent, action, risk) without exposing raw prompts.

---

## 7. Roadmap and “next work” framing

Authoritative phases: [ROADMAP.md](ROADMAP.md). Condensed:

| Phase | Focus |
|-------|--------|
| A–B | Foundation + co-pilot style intelligence (largely in place) |
| C | **System experience** — coherent product feel, observability, release alignment (**current**) |
| D | **Execution power** — dev agent depth, Ops, integrations, job lifecycle |
| E | **Agent ecosystem** — custom agents, templates, sharing |
| F | **Multimodal** (e.g. voice) |
| G | **Controlled autonomy** — smarter approvals, scheduling, long-running tasks |

**Backlog ideas** (not commitments) are listed at the bottom of `ROADMAP.md`.

**How to recommend next work:** Tie proposals to a **phase**, name **risks** (safety, permissions, cost), and point to **concrete code paths** and **docs** (setup, operations, workspace permissions). Avoid features that are “chat only” with no execution or observability (see roadmap guiding principle).

---

## 8. Where to go deeper (doc index)

| Need | Doc |
|------|-----|
| **How it’s built (layers, components)** | [ARCHITECTURE.md](ARCHITECTURE.md) |
| **Enterprise / platform diagram (positioning)** | [VISUAL_ARCHITECTURE.md](VISUAL_ARCHITECTURE.md) |
| **Where it’s going (phases)** | [ROADMAP.md](ROADMAP.md) |
| **Local install, Docker, LLM, API smoke** | [SETUP.md](SETUP.md) |
| **Web app behavior** | [WEB_UI.md](WEB_UI.md) |
| **Multi-user, BYOK, roles** | [MULTI_USER.md](MULTI_USER.md) |
| **Operator, always-on, host executor** | [OPERATIONS.md](OPERATIONS.md) |
| **Dev jobs** | [DEV_JOBS.md](DEV_JOBS.md), [DEV_JOB_FLOW.md](DEV_JOB_FLOW.md) |
| **Workspace + permissions** | [WORKSPACE_AND_PERMISSIONS.md](WORKSPACE_AND_PERMISSIONS.md) |
| **Cursor / contributor process** | [CURSOR_HANDOFF.md](CURSOR_HANDOFF.md) |
| **Product story (non-technical)** | [USERGUID.md](USERGUID.md) |
| **Recent install + web session handoff slice** | [HANDOFF_RECENT_WORK.md](HANDOFF_RECENT_WORK.md) |
| **Channel Gateway — design** | [CHANNEL_GATEWAY.md](CHANNEL_GATEWAY.md) |
| **Channel Gateway — execution plan** | [CHANNEL_GATEWAY_EXECUTION.md](CHANNEL_GATEWAY_EXECUTION.md) |

---

## 9. Verification expectations (typical)

Contributors and agents are expected to run checks after meaningful changes—see `.cursor/rules/finish-work-verification.mdc` and [SETUP.md](SETUP.md) (e.g. `python -m compileall -q app`, targeted `pytest`, restart API/bot when behavior changes).

---

## 10. What this overview intentionally does *not* do

- It does not list **every** file or endpoint; use **OpenAPI** (`/docs`) and **grep** for that.
- It does not document **your** production secrets, hostnames, or team process—only the **codebase’s** structure and public docs.
- It is a **snapshot**; when in doubt, trust **`main`** and the linked documents.

---

*For questions that are “what did we ship last week,” use [HANDOFF_RECENT_WORK.md](HANDOFF_RECENT_WORK.md) or `git log`. For “how do I run and ship,” use [DEVELOPMENT_HANDOFF.md](DEVELOPMENT_HANDOFF.md).*
