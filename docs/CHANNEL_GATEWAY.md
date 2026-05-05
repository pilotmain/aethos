# Channel Gateway — next-step design

**Status:** Partially implemented — Slack Events API + Bolt Socket Mode + Channel Gateway adapters ship in-repo; see [SLACK_SETUP.md](SLACK_SETUP.md). Broader “single adapter tree” refactor remains phased — [CHANNEL_GATEWAY_EXECUTION.md](CHANNEL_GATEWAY_EXECUTION.md).  
**Goal:** Extend Nexa from **Telegram + Web** into a **channel gateway platform** (Slack, WhatsApp, email, SMS, iMessage via providers, etc.) **without** weakening permissions, approval flow, audit/trust, or agent routing.

---

## Current state

From [HANDOFF_PLATFORM_OVERVIEW.md](HANDOFF_PLATFORM_OVERVIEW.md) and the codebase today:

- **Telegram** is tightly integrated with permissions, agents, dev jobs, and access control (`app/bot/telegram_bot.py`).
- **Slack** — HTTP endpoints under `/api/v1/slack/*` plus optional **Socket Mode** (`app/channels/slack/`, `NEXA_SLACK_ENABLED`).
- **Web UI:** sessions, trust activity, permission lifecycle (`web/`).
- **Backend:** service-layer architecture, execution safety and policy enforcement, audit and correlation IDs.
- **Bootstrap:** one-line install (`scripts/install.sh`, [SETUP.md](SETUP.md)).
- **Custom agents:** deterministic routing paths and regulated-domain safety where implemented.

**Gap:** Telegram is a **special-case integration**, not a reusable **channel** abstraction.

---

## Target architecture

```txt
Channel → Gateway → Nexa Core → Gateway → Channel
```

### New layer (proposed)

`app/services/channel_gateway/` — registry, routing, and shared utilities.

### Core interface (conceptual)

```python
class ChannelAdapter:
    def receive_event(self, raw_event): ...
    def normalize_message(self, raw_event): ...
    def send_message(self, user_id, message): ...
    def send_permission_card(self, user_id, payload): ...
    def map_user_identity(self, raw_event): ...
    def verify_signature(self, request): ...
```

Implementations: `TelegramAdapter`, `SlackAdapter`, … — each maps provider webhooks/APIs to the same contracts.

### Normalized message contract

All channels convert inbound events into a common shape (illustrative):

```json
{
  "channel": "slack | telegram | email | whatsapp",
  "channel_user_id": "...",
  "user_id": "...",
  "message": "...",
  "attachments": [],
  "metadata": {}
}
```

Downstream: existing **`web_chat_service`**, orchestration, permissions, and audit consume **normalized** messages, not raw Telegram types.

### Flow

1. Slack / WhatsApp / Email / Telegram (etc.) deliver an event.  
2. **Channel adapter** verifies, parses, maps identity.  
3. **Normalize** → existing pipeline (intent, `permission_request_flow`, agents, execution).  
4. **Response** path: adapter **sends** back on the same channel (text, cards, button callbacks as supported).

### Identity mapping

New persistence (proposal):

- **`ChannelUser`** (or equivalent): `id`, internal `user_id`, `channel`, `channel_user_id`, `created_at`, and any provider-specific fields needed for stable linking.

Links Telegram `user_id`, Slack `team_id+user`, email address, E.164 phone, etc. to the **same** internal Nexa user model used everywhere else.

### Permissions (non-negotiable)

Channels **must not** short-circuit governance.

All flows still go through:

`intent` → `permission_required` → **approve** → **execute** → **audit**

Adapters must support:

- **Permission card** rendering (or channel-appropriate equivalent).  
- **Approval callbacks** (buttons, slash-confirm, reply tokens — per channel).

The gateway is a **transport layer**, not a second permission system.

### Rules the gateway must obey

The Channel Gateway **must not**:

- Bypass **permissions** or **permission_request_flow**  
- Bypass **safety policy** or **enforcement**  
- Bypass **audit** / **trust** / **provenance**  
- Introduce “shadow” user IDs that skip `map_user_identity` and DB linkage  

---

## Effort (rough)

| Phase | Scope | Size (order of magnitude) |
|-------|--------|----------------------------|
| **1 — MVP gateway** (2–4 weeks) | Extract Telegram into an adapter; add **Slack** adapter; normalized contract; basic send/receive | ~2k–5k LOC |
| **2 — Production gateway** (6–10 weeks) | Channel registry; retry/delivery; webhook security; message state; unified permission UI mapping | ~8k–15k LOC |
| **3 — Enterprise gateway** (3–6 months) | Org-level channel controls; RBAC per channel; audit exports; compliance logging; SLAs; multi-tenant isolation | 25k+ LOC |

Estimates are indicative; validate against team and compliance needs.

---

## Channel difficulty (heuristic)

| Tier | Examples |
|------|----------|
| **Easier** | Telegram (already in repo), basic **email** |
| **Medium** | **Slack**, Gmail/Outlook (API + OAuth) |
| **Harder** | **WhatsApp Business API**, **SMS** (e.g. Twilio), **Apple Messages for Business** / iMessage via approved providers |

---

## Suggested implementation order

1. Extract **Telegram** → `TelegramAdapter` + shared types.  
2. Add **Slack** (most team demand, mature APIs).  
3. **Email** (inbound parse + outbound).  
4. **WhatsApp** (Meta Business rules, compliance).  
5. **iMessage** / Apple channel via **provider** (where contractually and technically available).

---

## Where to touch in this repo (when building)

| Area | Change |
|------|--------|
| `app/bot/telegram_bot.py` | Refactor toward `TelegramAdapter` + thin entrypoints |
| `app/services/web_chat_service.py` | Accept **normalized** channel messages; keep one core path |
| `app/services/permission_request_flow.py` (and related) | Channel-safe rendering hooks for cards/callbacks |
| `web/components/nexa/WorkspaceApp.tsx` | Optional: show **channel** origin on messages or sessions |
| `app/services/trust_audit_*` | Add **`channel`** field to events where missing |
| `app/models/` | `ChannelUser` (or equivalent) + migrations |

---

## Product positioning (after delivery)

Nexa becomes **gateway + governance** for AI agents across **communication channels**, not “only a Telegram bot + web app.”

**One-line summary:** Convert the Telegram integration into a **reusable Channel Gateway** so Nexa can operate across Slack, WhatsApp, email, and beyond **without** breaking the core governance model.

---

## Related docs

- [CHANNEL_GATEWAY_EXECUTION.md](CHANNEL_GATEWAY_EXECUTION.md) — phased execution plan (Telegram extract → router → Slack → email → audit/tests)  
- [ARCHITECTURE.md](ARCHITECTURE.md) — layers today  
- [VISUAL_ARCHITECTURE.md](VISUAL_ARCHITECTURE.md) — platform framing  
- [ROADMAP.md](ROADMAP.md) — phased direction  
- [WORKSPACE_AND_PERMISSIONS.md](WORKSPACE_AND_PERMISSIONS.md) — permission and workspace rules  
- [HANDOFF_PLATFORM_OVERVIEW.md](HANDOFF_PLATFORM_OVERVIEW.md) — repo map for agents  

---

*This document is the planning anchor for Channel Gateway work; update it when scope or sequencing changes.*
