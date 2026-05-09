# Marketplace & Assignment API — Permanent Fix Notes

This document aligns operator expectations with what the **AethOS / Nexa** codebase implements.

## 1. Marketplace 403 — “Telegram-linked owner”

**Behavior:** Install, uninstall, update, and **check updates now** require `get_valid_web_user_id` **and** `_require_owner` (Telegram-linked **owner** role). Non-owners receive **403** with detail:

`Marketplace install / uninstall / update require the Telegram-linked owner.`

**Fix for clients:** Mission Control must send **`X-User-Id`** and, when `NEXA_WEB_API_TOKEN` is set, **`Authorization: Bearer <token>`**. The Next.js helper `web/lib/api.ts` → `webFetch` / `configuredHeaders` reads these from **Login → Connection** (`readConfig()`).

**API aliases (same auth):**

| Alias | Canonical |
|-------|-----------|
| `GET /api/v1/marketplace/skills/search` | `GET /api/v1/marketplace/search` |
| `POST /api/v1/marketplace/check-updates` | `POST /api/v1/marketplace/-/check-updates-now` |

Registry URL is **`NEXA_CLAWHUB_API_BASE`** (see `Settings` / `.env.example`), not a separate `NEXA_SKILL_REGISTRY_URL`.

## 2. Search “does nothing”

**Backend:** Search is implemented at **`GET /api/v1/marketplace/search`** (plus **`/skills/search`** alias).

**Frontend:** `web/lib/api/marketplace.ts` → `searchSkills` now supports **category-only** queries (empty text but a category chip): it skips the early `return []` when a category is set.

## 3. Check updates 403

Same as §1 — **owner-only** by design. Use an owner `X-User-Id` or accept 403 for non-owner testers.

## 4. Assignment API — `assigned_to_handle` required

**Schema:** `AgentAssignmentCreate` (`app/schemas/agent_organization.py`) now accepts:

- `assigned_to_handle` / `agent_handle` (normalized like custom-agent keys), **or**
- `agent_id` (orchestration sub-agent id from `AgentRegistry`), **or**
- `task` / `title` to derive title and description.

Legacy-style bodies such as `{"agent_id": "<id>", "task": "…"}` validate after coercion.

## 5. Global / cross-session `@mention`

**Routing:** `app/services/sub_agent_router.py` uses **`resolve_agent_for_dispatch`**: resolve by **current chat** first, then **`get_agent_by_name_for_app_user`** so agents stamped with the owner (e.g. another web session scope) still match when `user_id` is present.

## Verification

- `pytest tests/test_marketplace_api_phase71.py tests/test_agent_assignment_schema.py tests/test_sub_agent_router.py tests/test_agent_assignment_auto_dispatch.py`
- Manual: set Connection user + bearer, open Marketplace — search and (as owner) check updates.
