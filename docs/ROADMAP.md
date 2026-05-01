# Nexa Roadmap (Arcturus)

Single source of truth for **where Nexa is going**. For how the system is built today, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Phase A — Foundation (done)

- Chat surfaces (Telegram + web)
- Agent routing and tool integration
- Core APIs and persistence
- Document generation pipeline
- Sessions and conversation context

---

## Phase B — Co-pilot intelligence (done / active)

- Next-step suggestions and follow-through
- Confirmation handling in natural language
- Multi-step flows with progress in context
- Work context surfaced to the user

---

## Phase C — System experience (current)

**Goal:** Make Nexa **feel like a coherent system**, not a disposable chat tab.

Includes (non-exhaustive):

- System events and inline observability
- Structured / mini-doc style responses where appropriate
- Release updates aligned with shipped behavior
- UI clarity without turning into a heavyweight dashboard

---

## Phase D — Execution power

- Expand **dev agent** depth and reliability
- Broaden **Ops** automation safely
- **External integrations** (APIs, webhooks, third-party services) where product and security allow
- Stronger **job lifecycle** (visibility, retries, cancellation, operator ergonomics)

---

## Phase E — Agent ecosystem

- **Custom agents** — deepen configuration and lifecycle (baseline exists today)
- **Templates** — reusable agent presets
- **Sharing** — optional export/import or team-visible definitions (deployment-dependent)
- **Marketplace** — distant optional horizon; requires trust, moderation, and billing clarity

---

## Phase F — Multimodal

- Voice input (**Telegram-first** is a natural fit)
- Audio responses where useful
- Video understanding — later / selective use cases only

See also: [ROADMAP_MULTIMODAL.md](ROADMAP_MULTIMODAL.md) for modality-specific notes if present.

---

## Phase G — Controlled autonomy

- Optional **auto-execution** for low-risk, well-scoped actions
- **Smarter approvals** — fewer prompts for boring paths, tighter gates for risky ones
- **Scheduled workflows** — time-based triggers aligned with operator and safety model
- **Long-running tasks** — durable execution with clear status surfaces

---

## Future enhancements (ideas backlog)

Not commitments — prioritize against [ARCHITECTURE.md](ARCHITECTURE.md) and deployment reality:

- Memory intelligence (auto recall and surfacing)
- Lightweight goal tracking without a heavy “project management” UI
- Cross-session intelligence and continuity
- Smart notifications (respectful volume)
- Workflow templates exposed through chat
- External API integration layer (auth, scopes, audit)
- Personal knowledge base ingestion (privacy-sensitive)
- **Multi-channel gateway** — Slack, email, WhatsApp, etc. via a shared adapter layer without bypassing permissions or audit; see [CHANNEL_GATEWAY.md](CHANNEL_GATEWAY.md) and phased [CHANNEL_GATEWAY_EXECUTION.md](CHANNEL_GATEWAY_EXECUTION.md)

---

## Guiding principle

> **Every feature should move Nexa toward being a system, not just a chat.**

If a proposal only adds conversational fluff without execution, observability, or user control—**rethink it**.
