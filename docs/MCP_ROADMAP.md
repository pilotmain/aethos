# MCP (Model Context Protocol) — roadmap

Nexa can connect specialized agents to external tools and data through a **standard connector** model. MCP is powerful; treat it as a **privilege boundary**, not a convenience shortcut.

## Goals

- Let **Dev**, **QA**, and (later) **Strategy** / **Ops** use approved tools in a repeatable way
- **Least privilege** by default: no broad filesystem, shell, or browser without explicit scope
- **Audit** every off-host or high-impact action; **redact** secrets; **time-bound** and **reversible** where possible

## Connector model (planned `tool_connector` registry)

| Concern | Notes |
|--------|--------|
| `key` | Stable id, e.g. `filesystem_project_read` |
| `connector_type` | `mcp` / `local` / `api` |
| `allowed_agents` / `allowed_actions` | Enforce in gateway before execution |
| `risk_level` + `requires_approval` | Gate in supervisor / Telegram approval |
| `is_enabled` | Kill switch per connector |

**Never allow by default:** unrestricted shell, unrestricted filesystem, blind browser automation, reading/writing production systems, or auto-approval of high-risk calls.

**Always require:** least privilege, audit logs, optional human approval, timeouts, redaction, and scope-limited connectors, routed through the **safe LLM / safe tool gateway** where user content is involved.

## Phased rollout

### Phase 1: Registry only

- Define `ToolConnector` in the database (or config seed)
- No real MCP process execution; surface **enabled** connectors in `/agents` and docs

### Phase 2: Safe local connectors

- Project file **read** (path allowlist), `git status`, test output, bounded logs
- All via **safe gateway** and existing `SAFE_LLM_*` / path rules

### Phase 3: External SaaS

- GitHub, Drive, Slack, calendar, email — per-connector OAuth, scopes, and audit

### Phase 4: MCP client adapter

- In-process or sidecar **MCP client** with connection budgets, per-call permissions, and structured audit of each MCP request/response (metadata only in logs; redact body where needed)

### Phase 5: Admin / product UI

- Enable/disable connectors, view recent tool calls, revoke access

## UX alignment

Telegram commands that mirror a future “Connectors” screen: e.g. `/dev health` (ops / worker), and future `/connectors` when the registry is wired. This file is **planning only** — no production MCP client ships with the initial registry-only phase.
