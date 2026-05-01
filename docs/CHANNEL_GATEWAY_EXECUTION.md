# Channel Gateway — Execution Plan (Final)

**Companion:** [CHANNEL_GATEWAY.md](CHANNEL_GATEWAY.md) (design)

---

## Goal

Implement Channel Gateway in Nexa with a single governed execution path across all channels.

**Supported direction:**

- Telegram  
- Slack  
- Email  
- WhatsApp  
- SMS  
- iMessage / Apple Messages for Business (via provider)  

All channels must use the same Nexa core.

One-line summary: Extract Telegram into a reusable ChannelAdapter and route all channels through the same governed Nexa core.

---

## Core Invariant

All traffic must follow:

```txt
intent → permission → approval → execution → audit → response
```

No bypass of:

- permissions  
- approvals  
- safety policy  
- provenance  
- audit  
- execution pipeline  

---

## Phase 0 — Rules

**Do not:**

- copy Telegram logic into other channels  
- create parallel bot stacks  
- bypass `web_chat_service` or orchestrator  
- embed channel logic inside agents  
- duplicate permission logic  
- allow adapters to execute tools directly  

---

## Phase 1 — Telegram Adapter

**Create:**

- `app/services/channel_gateway/`  

**Interface:**

```python
class ChannelAdapter:
    def receive_event(self, raw_event): ...
    def normalize_message(self, raw_event): ...
    def send_message(self, user_id, message): ...
    def send_permission_card(self, user_id, payload): ...
    def map_user_identity(self, raw_event): ...
    def verify_signature(self, request): ...
```

**Implement:**

- `app/services/channel_gateway/telegram_adapter.py`  

**Refactor:**

- `app/bot/telegram_bot.py` → thin wrapper  

**Responsibilities:**

- receive updates  
- normalize messages  
- map user identity  
- call router  
- send responses  
- render permission UI  

**Normalized contract:**

```json
{
  "channel": "telegram",
  "channel_user_id": "...",
  "user_id": "...",
  "message": "...",
  "attachments": [],
  "metadata": {}
}
```

---

## Phase 2 — Gateway Router

**Add:**

- `app/services/channel_gateway/router.py`  

```python
def handle_incoming_channel_message(msg):
    return web_chat_service.process_web_message(...)
```

**Router does not:**

- interpret intent  
- call tools  
- apply permissions  

---

## Phase 3 — Identity Mapping

**Model:** ChannelUser  

**Fields:**

- id  
- user_id  
- channel  
- channel_user_id  
- created_at  
- updated_at  

**Rules:**

- create on first message  
- reuse on subsequent  
- scoped per channel  
- no cross-channel collisions  

---

## Phase 4 — Permission Rendering

Each adapter implements:

`send_permission_card(user_id, payload)`

**Payload from:**

`permission_required_payload`

**Rendering:**

- Telegram → inline buttons  
- Slack → Block Kit  
- Email → links  
- WhatsApp → templates  
- SMS → links  

---

## Phase 5 — Slack Adapter

**Add:**

- `app/services/channel_gateway/slack_adapter.py`  

**Scope:**

- receive events  
- verify signature  
- normalize  
- send replies  
- support approvals  

**Env:**

- `SLACK_BOT_TOKEN`  
- `SLACK_SIGNING_SECRET`  

---

## Phase 6 — Email Adapter

**Add:**

- `app/services/channel_gateway/email_adapter.py`  

**Scope:**

- inbound email  
- normalize  
- send via SMTP  
- approval via links  

**Env:**

- `SMTP_HOST`  
- `SMTP_PORT`  
- `SMTP_USER`  
- `SMTP_PASSWORD`  
- `EMAIL_FROM`  

---

## Phase 7 — WhatsApp Adapter

**Add:**

- `app/services/channel_gateway/whatsapp_adapter.py`  

**Scope:**

- webhook  
- normalize  
- send replies  
- approval via templates/links  

**Env:**

- `WHATSAPP_ACCESS_TOKEN`  
- `WHATSAPP_PHONE_NUMBER_ID`  
- `WHATSAPP_VERIFY_TOKEN`  

---

## Phase 8 — Trust / Audit

**Add fields:**

- channel  
- channel_user_id  
- channel_message_id  
- channel_thread_id  

**Preserve:**

- workflow_id  
- run_id  
- execution_id  
- session_id  

---

## Phase 9 — UI (Optional)

- show message origin  
- filter trust activity by channel  
- show connected identities  

Backend must be complete first.

---

## Phase 10 — Tests

Validate:

1. normalization works  
2. router → core flow works  
3. permission renders correctly  
4. approval resumes execution  
5. audit includes channel  
6. identity mapping works  
7. signature verification works  
8. email approval resolves  
9. adapters cannot call tools  

---

## Effort

- Telegram extraction: 1–2 weeks  
- Router + identity + permission: 2–3 weeks  
- Slack: 1–2 weeks  
- Email: ~1 week  
- WhatsApp / SMS / iMessage: 2–6+ weeks  
- Enterprise hardening: 3–6 months  

---

## Architecture

```txt
Channels
    ↓
Channel Adapters
    ↓
Gateway Router
    ↓
Nexa Core
    ↓
Permissions / Agents / Execution / Audit
    ↓
Gateway Router
    ↓
Channel Adapter
    ↓
User
```

---

## Outcome

Nexa becomes a governed multi-channel AI execution gateway.

---

## Related Docs

- [CHANNEL_GATEWAY.md](CHANNEL_GATEWAY.md)  
- [WORKSPACE_AND_PERMISSIONS.md](WORKSPACE_AND_PERMISSIONS.md)  
- [HANDOFF_PLATFORM_OVERVIEW.md](HANDOFF_PLATFORM_OVERVIEW.md)  
