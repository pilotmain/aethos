# Nexa Architecture (Arcturus)

Single source of truth for **how Nexa is built today**. For direction and phases, see [ROADMAP.md](ROADMAP.md).

---

## 1. Vision

Nexa is **not** a generic chatbot. It is a **personal execution system** — software that thinks, plans, and acts **with** the user through conversation.

Core flow:

> Conversation → decision → execution → outcome

---

## 2. Core Principles

- **Chat-first** — No heavy UI builders; the primary surface is dialogue (web + Telegram).
- **Safe execution** — Risky or irreversible actions go through approval and clear gates where needed.
- **Composable agents** — Built-in specialists plus user-defined agents with scoped behavior.
- **Observable system** — Cost, decisions, tool use, jobs, and releases are visible, not hidden.
- **Minimal friction** — Prefer doing the right thing through chat over navigating complex chrome.

---

## 3. System Layers

### Interface layer

- **Web** — Next.js workspace (`web/`; primary shell: `WorkspaceApp`).
- **Telegram** — Mobile capture, commands, dev/Ops workflows, role-aware access.

Future surfaces (voice, CLI, etc.) stack on the same orchestration and execution core.

### Orchestration layer

Routes intent to behavior and agents:

- **`behavior_engine`** — Tone, context assembly, response shaping.
- **`agent_orchestrator`** — Agent routing and agent-specific flows.
- **`intent_classifier`** — Intent detection feeding routing decisions.

Responsibilities: interpret what the user wants, choose agent/tool vs plain response, and decide when execution (jobs, tools) is appropriate.

### Agent layer

**Built-in agents** (examples): default reasoning (`@nexa`-style paths), **`@dev`** (repo work through the job system), **`@ops`** (deployments / environment actions), **`@marketing`**, **`@research`**, **`@strategy`** — each with curated tools and copy.

**Custom agents** — Stored and driven via the user/agent model layer; created and refined through chat; scoped tools and behavior.

### Tool layer

Current capabilities include:

- **Public web access** — Read-only fetching and analysis of public URLs where enabled.
- **Web search** — Provider-backed discovery (e.g. Brave, Tavily, SerpAPI) when configured.
- **Document generation** — PDF, DOCX, Markdown, plain text via the document pipeline.
- **Dev executor** — Host-side or worker-side execution tied to **dev jobs** and review flows.

### Execution layer

- **Jobs** — Queued autonomous work (especially dev agent jobs) with statuses and payloads.
- **Approval flow** — Queue, approve/deny/review paths for risky or multi-step automation.
- **Operator / supervisor loop** — Host processes that keep workers and jobs healthy (see operational docs).

### Memory layer

- **`ConversationContext`** — Per-user (and per-session where applicable) chat state.
- **Flow state** — Lightweight multi-step flows (goal, steps, progress).
- **Sessions** — Web chat sessions and history wiring.
- **Preferences & soul-style files** — Long-lived tuning and patterns where configured.

### Observability layer

- **Usage tracking** — Tokens and calls attributed to turns and sessions.
- **Decision summary** — Transparent “why this agent / tool / risk” payloads to the client.
- **System events** — Inline rows for tools, jobs, documents, web usage.
- **Release updates** — User-facing changelog-driven highlights (web + optional Telegram `/updates`).

---

## 4. Agentic Components

### Decision system

Structured **decision summaries** (agent, action, tool, reason, risk, approval flags) explain routing without exposing hidden prompts or secrets.

### Co-pilot

**Next steps**, suggestion persistence, and lightweight confirmation handling (“yes”, “do the first one”) keep turns actionable without a separate task UI.

### Lightweight workflows

Multi-step flows tracked in context: goal, steps, progress — driven through natural language (“next”, “continue”, “where are we”) rather than a workflow builder.

### System events

Ephemeral rows in chat for tool runs, job creation/updates, document generation, web access lines — so the transcript reads as a **system log**, not only prose.

### Work context

Surfaces current flow, recent artifacts, and short “what’s happening” lines for the right panel / continuity between turns.

### Document system

Generate artifacts from assistant content and APIs; formats include PDF, DOCX, Markdown, text; export paths integrate with chat and storage layout.

### Web intelligence

Phased capability: public URL reading and summarization; search and source aggregation where configured; optional deeper browser-style preview depending on deployment settings.

---

## 5. UX Philosophy

### “System, not chat”

Responses should feel **structured**, **actionable**, and **purposeful** — closer to a small briefing than endless banter.

### Structured mini-doc responses

When helpful, answers trend toward sections such as summary, key points, recommendation, and next steps (exact shape depends on agent and intent).

### Progressive disclosure

Details (decisions, usage, doctor reports, release notes) appear **on demand** — collapsed, in side panels, or behind expanders — so the default view stays calm.

### Minimal UI

Avoid clutter and heavy dashboards; **chat remains the control layer**, with the web UI as a thin, inspectable shell around the same backend.

---

## 6. Security Model

- **Web API** — Requests validated with **`X-User-Id`** (and optional bearer token where configured); see security module and web routes.
- **Secrets** — API keys and tokens are **never** logged as plaintext in normal paths.
- **Isolation** — Tools and jobs run under explicit contracts; privileged paths require approval or owner-only capability.
- **Roles** — Owner vs default (and related) Telegram/web capabilities gate sensitive commands and cost visibility.
- **BYOK** — User-supplied provider keys stored encrypted at rest when used.

---

## 7. Cost Model

- **Tracking** — Per-turn and aggregate usage where the pipeline records LLM calls.
- **Estimation** — Cost estimates from token usage and configured pricing assumptions.
- **Optimization** — Prefer deterministic or tool-first paths when they satisfy the intent without an LLM call.

---

## 8. Current Capabilities (implemented)

Representative **today** — always verify against code and deployment flags:

- Multi-session **web chat** and Telegram chat
- **Agent routing** and **custom agents**
- **Web research** and **web search** (when enabled and keyed)
- **Marketing / analysis** surfaces where configured
- **Document generation** and export
- **Dev jobs** pipeline with review and approval semantics
- **Cost / usage** visibility for eligible users
- **Lightweight workflows** and **work context**
- **Structured decisions** and **system events** in the web UI
- **Release updates** (changelog-backed banner and `/updates`)

---

## Related docs

- Roadmap and phases: [ROADMAP.md](ROADMAP.md)
- Cursor / contributor handoff: [CURSOR_HANDOFF.md](CURSOR_HANDOFF.md)
- Web UI detail: [WEB_UI.md](WEB_UI.md)
- Setup: [SETUP.md](SETUP.md)
