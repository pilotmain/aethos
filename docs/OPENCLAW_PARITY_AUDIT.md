# OpenClaw parity audit — AethOS

**Phase 41+** — feature comparison against a typical “OpenClaw-style” local agent stack: multi-channel access, durable memory, autonomous runs, dev execution, system access, multi-agent dynamics, and media. Status is a snapshot for planning; see repository code and tests for ground truth.

**Principles we keep while closing gaps:** privacy-first, token efficiency, local-first execution, cost transparency.

---

## 1. Multi-Channel

| Channel   | Status | Notes |
|-----------|--------|--------|
| Telegram  | Done   | Production path via gateway; voice STT when multimodal flags on. |
| Web       | Done   | Next.js Mission Control + API. |
| Discord   | Partial| Adapter + `route_inbound`; optional bot when token + intents configured. |
| Slack     | Partial| Socket Mode bot; **default** `NEXA_SLACK_ROUTE_INBOUND=true` → `NexaGateway`. |
| WhatsApp  | Partial| Webhook + channel gateway (`app/services/channel_gateway/whatsapp_*`). |

## 2. Persistent Memory

| Feature            | Status  | Notes |
|--------------------|---------|--------|
| Markdown store     | Done    | `MemoryStore` per user. |
| Semantic search    | Partial | Pseudo- / optional embeddings; Ollama path in code. |
| Auto summarization | Partial | Mission summaries; optional post-mission intelligence pass. |

## 3. Autonomy

| Feature            | Status  | Notes |
|--------------------|---------|--------|
| Scheduler          | Done    | APScheduler + `NexaSchedulerJob`. |
| Heartbeat          | Partial | `run_heartbeat_cycle`; wizard enables `NEXA_HEARTBEAT_ENABLED=true`. |
| Long-running agents| Partial | `app/services/agents/long_running.py` + checkpoints. |

## 4. Dev Execution

| Feature         | Status  | Notes |
|-----------------|---------|--------|
| Dev runtime     | Done    | Workspaces, runs, jobs. |
| Run steering    | Partial | Pause/resume/cancel API + cooperative checks in `run_dev_mission`. |
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
| Voice / STT | Partial | Telegram voice → local/OpenAI STT; `NEXA_VOICE_ENABLED` + wizard defaults. |
| Vision / TTS | Partial | Gated multimodal orchestrator; privacy flags. |

## 8. Governance (OpenClaw-style)

| Feature | Status | Notes |
|---------|--------|--------|
| Consent grants | Partial | SQLite-backed `nexa_consent_grants`. |
| Activity ledger | Partial | SQLite hash chain `nexa_activity_ledger`. |
| Credential vault | Partial | Placeholder / keychain path documented. |

---

## Install / setup (OpenClaw-class UX)

| Path | Status | Notes |
|------|--------|--------|
| One-curl | Done | `install.sh` → clone/pull → **`scripts/setup.sh`** (colorful wizard). |
| Fast bootstrap | Opt-in | `scripts/install.sh --bootstrap-only` for CI/non-interactive. |

Recommended:

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/pilotmain/aethos@main/install.sh | bash
```

---

## Priority backlog

### Priority 1

1. Discord + Slack — operator docs + token verification in wizard status panel.
2. Full dev pipeline loop — strengthen iteration defaults and Mission Control visibility.
3. Browser automation (Playwright) — behind flags + URL policy.

### Priority 2

1. Long-running agents — scheduler ticks + gateway hook.
2. Memory auto-summarization — consolidation after missions.
3. Real embeddings (Ollama) — prefer over pseudo-embeddings when local model available.

### Priority 3

1. Mobile-first UX.
2. Signed skills marketplace at scale.

---

See also: [MIGRATING_FROM_OPENCLAW.md](MIGRATING_FROM_OPENCLAW.md), [OPENCLAW_SUCCESSOR_AUDIT.md](OPENCLAW_SUCCESSOR_AUDIT.md), `tests/test_openclaw_parity.py`.
