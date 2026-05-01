# OpenClaw parity audit — Nexa-next

**Phase 41** — feature comparison against a typical “OpenClaw-style” local agent stack: multi-channel access, durable memory, autonomous runs, dev execution, system access, multi-agent dynamics, and media. Status is a snapshot for planning; see repository code and tests for ground truth.

**Principles we keep while closing gaps:** privacy-first, token efficiency, local-first execution, cost transparency.

---

## 1. Multi-Channel

| Channel   | Status | Notes |
|-----------|--------|--------|
| Telegram  | Done   | Production path via gateway. |
| Web       | Done   | Next.js workspace + API. |
| Discord   | Partial| Adapter module + `route_inbound`; full bot install not in core path. |
| Slack     | Partial| `SlackChannel` + `route_inbound`; OAuth app deploy is operator-specific. |
| WhatsApp  | No     | Not implemented. |

## 2. Persistent Memory

| Feature            | Status  | Notes |
|--------------------|---------|--------|
| Markdown store     | Done    | `MemoryStore` per user. |
| Semantic search    | Partial | Pseudo- / optional embeddings; Ollama path documented in code. |
| Auto summarization | Partial | Mission summaries; optional post-mission intelligence pass. |

## 3. Autonomy

| Feature            | Status  | Notes |
|--------------------|---------|--------|
| Scheduler          | Done    | APScheduler + `NexaSchedulerJob`. |
| Heartbeat          | Partial | `run_heartbeat_cycle`; long-running tick optional. |
| Long-running agents| Partial | `app/services/agents/long_running.py` + checkpoints. |

## 4. Dev Execution

| Feature         | Status  | Notes |
|-----------------|---------|--------|
| Dev runtime     | Done    | Workspaces, runs, jobs. |
| Coding agents   | Partial | Adapters (incl. local stub, aider paths). |
| Full pipeline   | Partial | `run_dev_mission`: analyze → code → test → fix → repeat → commit (bounded). |

## 5. System Access

| Feature  | Status  | Notes |
|----------|---------|--------|
| Files    | Done    | Scoped reads / governance. |
| Shell    | Partial | Allowlisted commands. |
| Browser  | Partial | `browser_preview` + `system_access/browser_playwright` (gated). |

## 6. Multi-Agent

| Feature             | Status  | Notes |
|---------------------|---------|--------|
| Dynamic agents      | Done    | Phase 40 identity + runtime agents. |
| Parallel execution  | Partial | Missions / concurrency varies by workload. |
| Long-lived agents   | Partial | Long-running session module + scheduler hook. |

## 7. Media / Voice

| Feature | Status | Notes |
|---------|--------|--------|
| Voice / media | No | Not implemented. |

---

## Priority backlog (from Phase 41 spec)

### Priority 1

1. Discord + Slack channel adapters — expand beyond stubs (tokens, webhooks, verification).
2. Full dev pipeline loop — strengthen `run_dev_mission` phases and iteration defaults where safe.
3. Browser automation (Playwright) — `browser_playwright.py` behind flags + URL policy.

### Priority 2

1. Long-running agents — checkpoints + scheduler ticks.
2. Memory auto-summarization — consolidation after missions.
3. Better embeddings (Ollama) — swap in `memory/embedding.py`.

### Priority 3

1. Voice / media.
2. Mobile-first UX improvements.

---

## Nexa-next advantages (target)

- Stronger **privacy** and **BYOK** / local model paths.
- **Cost transparency** and usage surfaces.
- **Observable** runs in Mission Control vs opaque agent chatter.

This document should be updated when a row moves from partial to done.
