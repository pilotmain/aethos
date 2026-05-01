# Workspace registry and host permissions

Technical reference for **scoped host access**, **workspace roots**, and **environment flags** used when Nexa lists files, reads paths, or runs approval-gated host jobs (`local_tool` / host executor).

## `NEXA_WORKSPACE_STRICT`

| Value | Meaning |
| ----- | ------- |
| **Unset / `false`** (default) | **Recommended for most setups.** If you have **no** roots registered via `/workspace add`, paths are allowed when they fall under **`HOST_EXECUTOR_WORK_ROOT`** (defaults to the Nexa repo root). Explicit **chat approvals** for paths outside that tree can still resolve after grant (combined with grants and permission checks). |
| **`true`** | Stricter mode: when **no** workspace roots are registered, policy can **reject** paths until you register roots — **even if** you already have scoped **AccessPermission** grants. Use this only when you intentionally require **registered roots** for every meaningful path. |

**Do not** enable strict mode thinking it “fixes” Docker or arbitrary folders. For **Docker**, the API often sees **`HOST_EXECUTOR_WORK_ROOT=/app`** (the container tree). Listing host paths like `/Users/...` depends on **approvals**, **grant resolution**, and often **volume mounts** so those paths exist inside the container where `local_tool_worker` runs — strict mode does not substitute for that.

## Related flags (host permission cards and enforcement)

These control whether host intents run and whether missing grants produce **Allow once / Allow for session** flows (Web UI + API `permission_required`):

- **`NEXA_HOST_EXECUTOR_ENABLED`** — must be **`true`** for deterministic host/file intents and permission lifecycle. Default in code is **`false`**; set explicitly in `.env` when you trust this machine.
- **`NEXA_ACCESS_PERMISSIONS_ENFORCED`** — must be **`true`** for **permission requests** when no grant exists yet (structured cards). If **`false`**, precheck does not ask for grants the same way.

See `.env.example` (host executor section) and [SETUP.md](SETUP.md).

## Grant resolution vs workspace policy

Permission checks combine:

1. **Approved grants** (`AccessPermission`, scope such as `project_scan` / `file_read`) whose **target** covers the resolved absolute path.
2. **Workspace policy** (`path_allowed_under_policy`): registered roots and/or default work root.

Grant matching can apply **before** default-work-root policy when strict mode does not force “registration-only” behavior, so **resume-after-approve** (queue host job after Allow) works for explicitly approved targets outside the container default root (e.g. Docker **`/app`** vs host **`/Users/...`**).

## Docker and `local_tool`

The **API container** runs **`local_tool_worker`** when **`OPERATOR_AUTO_RUN_LOCAL_TOOLS=true`** (common default). Jobs execute with **`HOST_EXECUTOR_WORK_ROOT`** from `.env` as seen **inside the container**. To operate on host directories, either mount them into the container and align **`HOST_EXECUTOR_WORK_ROOT`**, or run the worker/API in an environment that shares the host filesystem.

## Web UI identity

The Web chat and permission endpoints expect a valid **`X-User-Id`** (typically **`tg_<telegram_user_id>`**) configured in the browser app — not an `.env` variable. See [WEB_UI.md](WEB_UI.md).

## After “Allow” on a permission card (Web)

When you approve an **access permission** request, the API resumes the pending host payload and enqueues a **`local_tool`** / **host-executor** job with **`approval_required=false`** so it enters **`queued`** immediately (the chat permission replaces the separate Job-tab approval step for that action).

The approve response includes **`host_job_id`** (and **`related_jobs`**) so the Web UI can **`GET /api/v1/web/jobs/{id}`** until the job completes and show the **result** without another message.

Phrases like **“any update”**, **“status”**, or **“job status”** are answered **deterministically** from the latest host-executor job tied to **`chat_origin.web_session_id`** for this chat session — not from an LLM guess — so status matches the Web session rather than unrelated jobs.
