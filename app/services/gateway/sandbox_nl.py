# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Gateway NL: LLM-generated execution plan → user approval → sandbox executor."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.conversation_context_service import get_or_create_context
from app.services.gateway.context import GatewayContext
from app.services.sandbox.plan_executor import SandboxExecutor, format_sandbox_results
from app.services.user_capabilities import is_privileged_owner_for_web_mutations

_EXEC_WORD = re.compile(
    r"\b(add|remove|change|update|modify|set|replace|delete|create|install|refactor|migrate|fix|apply)\b",
    re.IGNORECASE,
)

_AFFIRMATIVE = frozenset(
    {
        "yes",
        "y",
        "approve",
        "approved",
        "execute",
        "run",
        "go ahead",
        "go",
        "ok",
        "okay",
        "confirm",
        "do it",
        "run it",
    }
)
_NEGATIVE = frozenset({"no", "n", "cancel", "cancelled", "abort", "stop"})

_MAX_DEV_READ_CHARS = 100_000

_RE_DEV_READ = re.compile(
    r"^(?:development|dev)\s+(read|show|cat|display)\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_RE_DEV_WRITE = re.compile(
    r"^(?:development|dev)\s+write\s+(\S+)\s+with\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)


def _resolve_workspace_read_path(root: Path, spec: str, todo: Path | None) -> Path | None:
    """Resolve ``spec`` to a single file under ``root`` (todo project preferred for bare names)."""
    rel = spec.strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in Path(rel).parts:
        return None
    root = root.resolve()
    candidates: list[Path] = []
    if todo is not None:
        candidates.append((todo / rel).resolve())
    candidates.append((root / rel).resolve())
    seen: set[str] = set()
    for p in candidates:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        try:
            p.relative_to(root)
        except ValueError:
            continue
        if p.is_file():
            return p
    return None


def try_sandbox_development_file_fastpath(
    gctx: GatewayContext,
    raw_message: str,
    db: Session,
) -> dict[str, Any] | None:
    """
    ``Development read|show|cat|display <path>`` — read a workspace file without LLM.

    Runs when sandbox execution is enabled and the caller is a privileged owner (same gate as
    other sandbox NL). Intended to run **before** :func:`try_development_nl_gateway_turn` in the gateway.
    """
    s = get_settings()
    if not bool(getattr(s, "nexa_sandbox_execution_enabled", False)):
        return None
    raw = (raw_message or "").strip()
    uid = (gctx.user_id or "").strip()
    if not raw or not uid or raw.startswith("/"):
        return None
    if not is_privileged_owner_for_web_mutations(db, uid):
        return None
    if not bool(getattr(s, "nexa_auto_approve_owner", True)):
        return None

    first = raw.splitlines()[0].strip()
    root_str = _workspace_root_for_sandbox()
    if not root_str:
        return None
    root = Path(root_str).expanduser().resolve()
    if not root.is_dir():
        return None

    from app.services.gateway.development_nl import _latest_todo_project

    todo = _latest_todo_project(root)

    wm = _RE_DEV_WRITE.match(first)
    if wm:
        rel = wm.group(1).strip().strip("`\"'")
        content = (wm.group(2) or "").strip()
        if not rel or ".." in Path(rel.replace("\\", "/")).parts:
            return None
        mx = int(getattr(s, "nexa_sandbox_execution_max_file_bytes", 1_048_576))
        if len(content.encode("utf-8", errors="replace")) > mx:
            from app.services.gateway.runtime import gateway_finalize_chat_reply

            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply(
                    f"Content exceeds sandbox max file size ({mx} bytes).",
                    source="sandbox_dev_write_too_large",
                    user_text=raw,
                ),
                "intent": "sandbox_dev_write_too_large",
            }
        dest = (root / rel.replace("\\", "/").lstrip("/")).resolve()
        try:
            dest.relative_to(root)
        except ValueError:
            from app.services.gateway.runtime import gateway_finalize_chat_reply

            return {
                "mode": "chat",
                "text": gateway_finalize_chat_reply(
                    "Path must stay under the configured workspace root.",
                    source="sandbox_dev_write_bad_path",
                    user_text=raw,
                ),
                "intent": "sandbox_dev_write_bad_path",
            }
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        from app.services.gateway.runtime import gateway_finalize_chat_reply

        body = (
            f"**Wrote file** `{rel}` ({len(content)} chars).\n\n"
            f"_Resolved path:_ `{dest}`"
        )
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(body.strip(), source="sandbox_dev_write", user_text=raw),
            "intent": "sandbox_dev_write",
        }

    m = _RE_DEV_READ.match(first)
    if not m:
        return None
    spec = (m.group(2) or "").strip().strip("`\"'")
    if not spec:
        return None

    path = _resolve_workspace_read_path(root, spec, todo)
    from app.services.gateway.runtime import gateway_finalize_chat_reply

    if path is None:
        tried = f"`{spec}`"
        if todo is not None:
            tried += f" (also under latest scaffold `{todo.name}`)"
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(
                f"**File not found** — {tried}\n\n"
                "Use a path relative to your workspace root or a file inside the latest todo-style folder.",
                source="sandbox_dev_read_not_found",
                user_text=raw,
            ),
            "intent": "sandbox_dev_read_not_found",
        }

    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(
                f"Could not read file: {e}",
                source="sandbox_dev_read_error",
                user_text=raw,
            ),
            "intent": "sandbox_dev_read_error",
        }
    if len(data) > _MAX_DEV_READ_CHARS:
        data = data[:_MAX_DEV_READ_CHARS] + "\n\n… [truncated]"
    rel_disp = str(path.relative_to(root)) if path.is_relative_to(root) else path.name
    body = f"**{path.name}** (`{rel_disp}`)\n\n```\n{data}\n```"
    return {
        "mode": "chat",
        "text": gateway_finalize_chat_reply(body.strip(), source="sandbox_dev_read", user_text=raw),
        "intent": "sandbox_dev_read",
    }


def _workspace_root_for_sandbox() -> str:
    s = get_settings()
    override = str(getattr(s, "nexa_sandbox_execution_workspace", "") or "").strip()
    if override:
        return override
    return str(getattr(s, "nexa_workspace_root", "") or "").strip()


def _telegram_user_id(gctx: GatewayContext) -> int | None:
    tg_id = gctx.extras.get("telegram_user_id")
    if isinstance(tg_id, int):
        return tg_id
    if isinstance(tg_id, str) and tg_id.strip().isdigit():
        return int(tg_id.strip())
    return None


def try_sandbox_approve_gateway_turn(
    gctx: GatewayContext,
    raw_message: str,
    db: Session,
) -> dict[str, Any] | None:
    """Handle yes/no for a pending sandbox plan stored on conversation context."""
    if not bool(getattr(get_settings(), "nexa_sandbox_execution_enabled", False)):
        return None
    raw = (raw_message or "").strip()
    uid = (gctx.user_id or "").strip()
    if not raw or not uid:
        return None
    if not is_privileged_owner_for_web_mutations(db, uid):
        return None

    ws_id = str(gctx.extras.get("web_session_id") or "default").strip()[:64] or "default"
    cctx = get_or_create_context(db, uid, web_session_id=ws_id)
    pending_raw = (getattr(cctx, "sandbox_pending_plan_json", None) or "").strip()
    if not pending_raw:
        return None

    tlow = raw.lower().strip()
    if tlow in _NEGATIVE:
        cctx.sandbox_pending_plan_json = None
        db.add(cctx)
        db.commit()
        from app.services.gateway.runtime import gateway_finalize_chat_reply

        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(
                "Sandbox plan **cancelled**. Send a new request when you want another plan.",
                source="sandbox_cancelled",
                user_text=raw,
            ),
            "intent": "sandbox_plan_cancelled",
        }

    if tlow not in _AFFIRMATIVE:
        return None

    try:
        envelope = json.loads(pending_raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        cctx.sandbox_pending_plan_json = None
        db.add(cctx)
        db.commit()
        return None

    plan = envelope.get("plan") if isinstance(envelope, dict) else None
    if not isinstance(plan, dict):
        cctx.sandbox_pending_plan_json = None
        db.add(cctx)
        db.commit()
        return None

    root = _workspace_root_for_sandbox()
    if not root:
        from app.services.gateway.runtime import gateway_finalize_chat_reply

        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(
                "Sandbox is enabled but **NEXA_WORKSPACE_ROOT** (or **NEXA_SANDBOX_EXECUTION_WORKSPACE**) "
                "is not set on this host.",
                source="sandbox_config_error",
                user_text=raw,
            ),
            "intent": "sandbox_config_error",
        }

    s = get_settings()
    executor = SandboxExecutor(
        root,
        max_file_bytes=int(getattr(s, "nexa_sandbox_execution_max_file_bytes", 1_048_576)),
        command_timeout_seconds=int(getattr(s, "nexa_sandbox_execution_command_timeout_seconds", 60)),
    )
    out = executor.execute_plan(plan, user_id=uid)
    cctx.sandbox_pending_plan_json = None
    db.add(cctx)
    db.commit()

    from app.services.gateway.runtime import gateway_finalize_chat_reply

    if out.get("success"):
        body = "**Sandbox execution complete**\n\n" + format_sandbox_results(list(out.get("results") or []))
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(body.strip(), source="sandbox_executed", user_text=raw),
            "intent": "sandbox_executed",
        }
    msg = str(out.get("message") or "Execution failed.")
    body = f"**Sandbox run failed**\n\n{msg}\n\n" + format_sandbox_results(list(out.get("results") or []))
    return {
        "mode": "chat",
        "text": gateway_finalize_chat_reply(body.strip(), source="sandbox_failed", user_text=raw),
        "intent": "sandbox_failed",
    }


def try_sandbox_plan_gateway_turn(
    gctx: GatewayContext,
    raw_message: str,
    db: Session,
) -> dict[str, Any] | None:
    """Ask the LLM for a JSON plan and store it pending explicit approval."""
    s = get_settings()
    if not bool(getattr(s, "nexa_sandbox_execution_enabled", False)):
        return None
    if not bool(getattr(s, "use_real_llm", False)):
        return None
    raw = (raw_message or "").strip()
    uid = (gctx.user_id or "").strip()
    if not raw or not uid or raw.startswith("/"):
        return None
    if not is_privileged_owner_for_web_mutations(db, uid):
        return None
    if not bool(getattr(s, "nexa_auto_approve_owner", True)):
        return None

    if not _EXEC_WORD.search(raw):
        return None
    if len(raw) > 2_000:
        return None

    ws_id = str(gctx.extras.get("web_session_id") or "default").strip()[:64] or "default"
    cctx = get_or_create_context(db, uid, web_session_id=ws_id)
    if (getattr(cctx, "sandbox_pending_plan_json", None) or "").strip():
        return None

    root = _workspace_root_for_sandbox()
    if not root:
        return None

    root_path = Path(root).expanduser().resolve()
    todo_hint = ""
    try:
        from app.services.gateway.development_nl import _latest_todo_project

        todo = _latest_todo_project(root_path)
        if todo is not None:
            rel_todo = todo.resolve().relative_to(root_path).as_posix()
            todo_hint = (
                f"Detected todo-style app folder (relative to workspace): `{rel_todo}/`\n"
                f"Prefer read/write paths like `{rel_todo}/styles.css` when changing that app "
                "(still relative to workspace — never use host absolute paths or `..`).\n"
            )
    except ValueError:
        todo_hint = ""

    schema = """{
  "explanation": "string",
  "actions": [
    {"type": "read_file", "params": {"path": "relative/path/under/workspace"}},
    {"type": "write_file", "params": {"path": "relative/path", "content": "full new file text"}},
    {"type": "run_command", "params": {"command": "npm install", "cwd": "relative/subdir or ."}},
    {"type": "open_browser", "params": {"url": "http://localhost:3000/ or file:///…"}}
]
}"""

    system = (
        "You are AethOS sandbox planner. Output ONLY valid JSON matching the requested shape.\n"
        "All file paths must be relative to the workspace root (no absolute paths, no '..').\n"
        f"{todo_hint}"
        "Prefer the smallest sequence: read only if needed, then writes, then at most one run_command.\n"
        "Commands: first token must be one of npm, npx, yarn, pnpm, git, python, python3, node, "
        "ls, cat, echo, mkdir, touch, cp, mv, pwd, head, tail, wc. No pipes, no semicolons, no rm, "
        "no sudo, no curl/wget, no bash -c.\n"
        f"Workspace root on host: {root}\n"
    )

    from app.services.safe_llm_gateway import safe_llm_json_call

    try:
        plan = safe_llm_json_call(
            system_prompt=system,
            user_request=raw[:4000],
            extra_text=None,
            schema_hint=schema,
            db=db,
            telegram_user_id=_telegram_user_id(gctx),
        )
    except Exception:
        return None

    if not isinstance(plan, dict):
        return None
    actions = plan.get("actions")
    if not isinstance(actions, list) or not actions:
        return None

    from app.services.sandbox.action_allowlist import validate_plan_actions

    ok, errs = validate_plan_actions(
        plan,
        workspace_root=Path(root).expanduser().resolve(),
        max_file_bytes=int(getattr(s, "nexa_sandbox_execution_max_file_bytes", 1_048_576)),
    )
    if not ok:
        from app.services.gateway.runtime import gateway_finalize_chat_reply

        msg = "I drafted a plan but it did not pass safety validation:\n" + "\n".join(f"- {e}" for e in errs)
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(msg, source="sandbox_plan_invalid", user_text=raw),
            "intent": "sandbox_plan_invalid",
        }

    envelope = {"plan": plan, "user_text": raw, "workspace_root": root}
    cctx.sandbox_pending_plan_json = json.dumps(envelope, default=str)[:100_000]
    db.add(cctx)
    db.commit()

    from app.services.gateway.runtime import gateway_finalize_chat_reply

    expl = str(plan.get("explanation") or "Proposed workspace changes.").strip()
    lines = []
    for i, a in enumerate(actions, start=1):
        if not isinstance(a, dict):
            continue
        typ = str(a.get("type") or "")
        params = a.get("params") if isinstance(a.get("params"), dict) else {}
        detail = params.get("command") or params.get("path") or params.get("url") or "—"
        lines.append(f"{i}. **{typ}** — `{str(detail)[:200]}`")

    body = (
        f"**Sandbox plan (pending your approval)**\n\n_{expl}_\n\n"
        + "\n".join(lines)
        + "\n\nReply **yes** to execute inside the configured workspace, or **no** to cancel.\n"
        "_This path is owner-only and uses an allowlisted executor (no arbitrary shell)._"
    )
    return {
        "mode": "chat",
        "text": gateway_finalize_chat_reply(body.strip(), source="sandbox_plan_pending", user_text=raw),
        "intent": "sandbox_plan_pending",
    }


__all__ = [
    "try_sandbox_approve_gateway_turn",
    "try_sandbox_development_file_fastpath",
    "try_sandbox_plan_gateway_turn",
]
