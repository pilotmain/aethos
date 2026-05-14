# AethOS — Software Design Document (SDD)

**Version:** 2.0  
**Date:** 2026-05-14  
**Status:** Draft — sections tagged `[Implemented]`, `[Target]`, or `[Release TBD]` per below.

> This document describes architecture and behavior aligned with the repository.  
> **`[Implemented]`** — verified against current modules (paths cited).  
> **`[Target]`** — agreed direction or product intent; confirm against code before treating as normative.  
> **`[Release TBD]`** — version-specific behavior to be filled when verified.

---

## 1. Introduction

### 1.1 Purpose `[Implemented]`

AethOS is an **agentic operating system**: natural language drives orchestration, host-local tools (files, allowlisted commands, browser open/screenshot), sub-agents, Mission Control, and optional cloud hooks when the operator supplies credentials.

### 1.2 Product stance: “free” and privacy `[Implemented]`

- **No subscription fee** for AethOS itself.  
- **Local-first execution** for host tools and workspace paths where configured.  
- **Optional paid vendor services** (remote LLM APIs, web search APIs, cloud deploy CLIs) require **user-provided keys** and are gated by settings and permissions.

### 1.3 Scope `[Implemented]`

| Area | Primary modules |
|------|------------------|
| HTTP API | `app/main.py`, `app/api/routes/*` |
| Chat gateway | `app/services/gateway/runtime.py`, `app/api/routes/mission_control.py` |
| Intent / NL | `app/services/intent_classifier.py`, `app/services/host_executor_intent.py`, `app/services/host_executor_nl_chain.py` |
| Host execution | `app/services/host_executor.py`, `app/services/host_executor_chat.py`, `app/services/command_executor_worker.py` |
| Browser (open/screenshot) | `app/services/browser_automation.py` |
| Agents | `app/services/sub_agent_registry.py`, `app/services/sub_agent_executor.py`, `app/services/inter_agent_coordinator.py`, `app/api/routes/agent_spawn.py` |
| Soul versioning | `app/services/soul_manager.py`, `app/services/gateway/soul_versioning_nl.py` |
| LLM | `app/services/llm/bootstrap.py`, `app/services/llm/completion.py`, `app/core/config.py` (`Settings`) |

### 1.4 Definitions `[Implemented]`

| Term | Definition |
|------|------------|
| **Agent** | Orchestration sub-agent (registry row + executor); distinct from “LLM” or “custom agent” SQL entities where applicable. |
| **Host executor** | Allowlisted local actions (`host_action` payloads) executed after validation / approvals / jobs. |
| **Workspace** | Directory roots and project registry for file and command resolution (`app/services/workspace_registry.py`, `nexa_workspace_project_registry`). |
| **Soul** | Persistent persona / markdown; per-user DB-backed content with versioned snapshots (see §4.4). |
| **Sandbox** | See §5 — multiple meanings; do not overload the word without qualifier. |

---

## 2. System requirements

### 2.1 Functional requirements `[Implemented]` (high level)

| ID | Requirement | Notes |
|----|-------------|--------|
| FR-01 | Create / list / control agents via API and NL | `agent_spawn`, gateway, Telegram |
| FR-02 | Assign work via @mention / NL | `sub_agent_executor`, `inter_agent_coordinator` |
| FR-03 | Read / write files under workspace policy | `host_executor`, `host_executor_intent`, `local_file_intent` |
| FR-04 | Run allowlisted commands | `host_executor` + `run_command` / `run_name` |
| FR-05 | Open URLs (system browser) | `browser_automation.open_system_browser` |
| FR-06 | Screenshots (OS capture) | `browser_automation.take_system_screenshot` |
| FR-07 | Optional deploy NL / CLI | `nexa_generic_deploy_enabled` and related NL modules |
| FR-08 | Soul history / rollback NL | `soul_versioning_nl.py`, `soul_manager.py`, `MemoryService` |

### 2.2 Non-functional requirements `[Target]` + reference machine

Benchmarks are **not CI-enforced** in this document unless separately added. Measure on:

| Component | Spec |
|-----------|------|
| Machine | MacBook Air/Pro, Apple M1 (2020 class), 8 GB RAM |
| OS | macOS 14.x |
| Filesystem | Internal SSD, APFS |
| Python | 3.11.x |
| Optional local LLM | Ollama with a pinned small model (e.g. `gemma2:2b`) when testing local inference |

| ID | Requirement | Measurement `[Target]` |
|----|-------------|-------------------------|
| NFR-01 | Gateway turn (server-side `POST …/gateway/run` processing) | Document p50/p95 after profiling; not including browser TLS |
| NFR-02 | Small file write under host executor | Order-of-magnitude ms on reference machine |
| NFR-03 | Idle RAM (API only) | Measure with typical `.env` |
| NFR-04 | RAM with Ollama + model | Measure with pinned model |

**Explicit non-goals for local OSS:** no **99.9% SLA** claim for a single laptop process without defining hosting.

### 2.3 Default experience vs configuration `[Target]`

The following is **product intent**; verify against `Settings`, `.env.example`, and gateway before marking `[Implemented]` for a named release.

| Scenario | Desired behavior |
|----------|------------------|
| No cloud LLM keys, Ollama not running | Safe degradation: pattern / lightweight routing without paid APIs (exact path: verify `use_real_llm`, `nexa_llm_provider`, fallbacks). |
| Ollama running | Prefer local HTTP provider (`ollama` slug in LLM bootstrap). |
| Cloud keys present | Use Anthropic / OpenAI / etc. per `NEXA_LLM_PROVIDER` and keys. |

**Action item `[Release TBD]`:** Reconcile `.env.example` (`USE_REAL_LLM`, keys) with this table once verified.

---

## 3. Architecture

### 3.1 Layering (client vs server) `[Implemented]`

```text
┌─────────────────────────────────────────────────────────────┐
│ Client layer                                                │
│   Web browser (Next.js Mission Control)  │  Telegram app  │
└───────────────────────────┬────────────────────────┬────────┘
                            │ HTTPS / WS           │ Telegram API
                            ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│ Server: FastAPI (`app.main:app`)                             │
│   CORS, metrics, security middleware                          │
│   Routers under `{API_V1_PREFIX}` (default `/api/v1`)       │
│   Gateway runtime (`app/services/gateway/runtime.py`)       │
│   Host executor, jobs, permissions, agents, …                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Host OS: workspace dirs, sqlite DB files, optional Ollama   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Request path (chat) `[Implemented]`

Typical Mission Control chat:

1. Browser → `POST /api/v1/mission-control/gateway/run` (`mission_control.py`).  
2. `gateway/runtime.py` composes context, permissions, deterministic branches (host executor NL, goals, soul NL, …), then LLM / templates as applicable.  
3. Mutations that touch disk or shell go through **`host_executor`** (sync or queued jobs depending on entrypoint), not ad-hoc subprocess from LLM output.

### 3.3 Component → repository mapping `[Implemented]`

| SDD concept | Code |
|-------------|------|
| Gateway | `app/services/gateway/runtime.py`, helpers under `app/services/gateway/` |
| Intent classification | `app/services/intent_classifier.py` + gateway branches |
| Host “tool” execution | `app/services/host_executor.py`, `host_executor_chat.py`, `access_permissions.py` |
| Command execution (worker) | `app/services/command_executor_worker.py` (job worker consuming approved payloads) |
| Browser open / screenshot | `app/services/browser_automation.py` |
| File NL → payload | `app/services/host_executor_intent.py`, `local_file_intent.py` |
| NL browser chains | `app/services/host_executor_nl_chain.py` |
| Agent registry / execute | `sub_agent_registry.py`, `sub_agent_executor.py`, `agent_spawn` routes |
| Inter-agent handoff NL | `inter_agent_coordinator.py` |
| Workspace roots (HTTP) | `app/api/routes/web.py` (`/web/workspace/roots`, …) |

### 3.4 API surface (representative) `[Implemented]`

Authoritative list: **`/docs`** and **`/openapi.json`** on a running API, or `app/main.py` `include_router` table.

| Method | Path (prefix `/api/v1` unless noted) | Role |
|--------|--------------------------------------|------|
| GET | `/health` | Liveness |
| POST | `/mission-control/gateway/run` | Main Mission Control chat gateway |
| GET | `/agents/list` | List orchestration agents |
| POST | `/agents/create` (also `/agents/spawn`) | Create/spawn agents |
| POST | `/agents/execute/{agent_name}` | Execute registered agent |
| GET/POST | `/web/workspace/roots` | Workspace root registry |
| GET | `/user/settings` | User settings |
| GET | `/enterprise-audit/recent` | Owner-gated audit JSONL |
| * | `/clawhub/*` | ClawHub / marketplace integration API |
| * | `/marketplace/*` | Mission Control marketplace panel API |

Many more routers exist (cron, jobs, approvals, self-improvement, …); do not treat this table as exhaustive.

### 3.5 Phase 5 — optional local quantized LLM `[Target]`

- **Not implemented** as a separate GGUF engine in this repo today.  
- **Today:** remote HTTP providers + **`ollama`** as the local HTTP backend (`app/services/llm/providers/ollama_backend.py`, registered from `bootstrap.py`).  
- **Direction:** any future local engine should appear as **another provider in the same registry / `NEXA_LLM_PROVIDER` enum**, with an ADR naming the slug (`local_gguf`, etc.) — do not document a literal `local` slug until it exists in `Settings` validation.

---

## 4. Detailed design

### 4.1 Host executor `[Implemented]`

- Single gate for allowlisted actions: `execute_payload` in `host_executor.py`.  
- Chat offers / confirmations: `host_executor_chat.py`.  
- Chains: `host_action: chain` with inner allowlist (`host_executor_chain.py`).

### 4.2 Browser automation `[Implemented]`

- **`browser_open`:** system default browser (`open` / `xdg-open` / `os.startfile`) — `open_system_browser`.  
- **`browser_screenshot`:** OS capture (`take_system_screenshot`); brief delay before capture to allow tabs to paint.  
- **Click / fill (optional):** may still use Playwright sync session where enabled; document separately from “stable open/screenshot” path.

### 4.3 LLM stack `[Implemented]` (current)

- Provider chain built in `llm/bootstrap.py` / `completion.py`.  
- Configuration via `app/core/config.py` (`Settings`): keys, `NEXA_LLM_PROVIDER`, models, Ollama base URL, etc.

### 4.4 Soul history and rollback `[Implemented]`

**Per-user soul (DB + snapshots)**

- Snapshot directory: `~/.aethos/soul_history/<safe_user_id>/`.  
- Filename stamp: `datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")` → example stem `2026-05-14_14-30-00_123456` (microsecond resolution).  
- Before overwriting soul text, previous content is written under that directory (`snapshot_user_soul_before_write` in `soul_manager.py`).

**Repo soul file**

- Repo snapshots live under `docs/development/soul_history/` (`repo_soul_history_dir`), tied to `docs/development/soul.md` — distinct from per-user history.

**Rollback (chat NL)**

- `try_soul_versioning_nl_turn` in `soul_versioning_nl.py` handles `soul_history`, `soul_rollback`, `soul_rollback_previous`.  
- Rollback loads markdown via `read_user_soul_version`, then persists through **`MemoryService.update_soul_markdown`** (`record_history=True`), `db.commit()`.

---

## 5. Security and sandboxes `[Implemented]` / `[Target]`

| Sandbox term | Meaning | Where |
|--------------|---------|--------|
| Policy / approval | Host actions require validation + approvals / auto-approve rules | `host_executor_chat.py`, `access_permissions.py`, `nexa_safety_policy` |
| Marketplace skill sandbox | Skill install / execute constraints | Marketplace + skill installer paths (`nexa_marketplace_sandbox_mode`, etc.) |
| Full execution VM isolation | Strong isolation for arbitrary code | **`[Target]`** — not the default for host executor today |

Threats: path traversal (mitigated by `safe_relative_path` and roots), arbitrary shell (denied — allowlists only), secret egress (optional enforcement flags in `Settings`).

---

## 6. Governance of this document `[Target]`

- **Architectural PRs** should update `docs/DESIGN.md` **or** include a PR comment explaining why the doc was not updated.  
- **CI:** optional non-blocking check (e.g. reminder when `gateway/runtime.py` or `host_executor.py` changes without doc touch). Avoid brittle “version file must match” gates.  
- **Review:** at least one reviewer familiar with gateway + host executor.

---

## 7. Revision history

| Version | Date | Notes |
|---------|------|--------|
| 2.0 | 2026-05-14 | Draft: codebase-aligned vocabulary, routes, soul + browser detail, governance. |
| 1.x | (prior drafts) | Superseded — generic diagrams / incorrect API names. |

---

## Appendix A — Mermaid overview `[Implemented]` (conceptual)

```mermaid
flowchart TB
  subgraph clients [Clients]
    WEB[Mission Control Web]
    TG[Telegram]
  end
  subgraph api [FastAPI app.main]
    GW[mission_control gateway/run]
    RT[gateway runtime]
    HE[host_executor]
    AG[agents routes + sub_agent_executor]
  end
  subgraph data [Persistence]
    DB[(SQLite)]
    FS[Workspace FS]
  end
  WEB --> GW
  TG --> GW
  GW --> RT
  RT --> HE
  RT --> AG
  HE --> FS
  AG --> DB
  RT --> DB
```

---

*End of SDD v2.0 draft.*
