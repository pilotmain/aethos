"""User-facing copy and safe status fields for host executor (visibility only — no execution)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT, get_settings
from app.services.host_executor import ALLOWED_RUN_COMMANDS


def _resolved_work_root() -> str:
    s = get_settings()
    raw = (getattr(s, "host_executor_work_root", None) or str(REPO_ROOT)).strip()
    try:
        return str(Path(raw).expanduser().resolve())
    except OSError:
        return str(REPO_ROOT)


def allowed_tool_human(payload: dict[str, Any]) -> str:
    """Single-line description of the allowlisted tool (no user-controlled argv)."""
    act = (payload.get("host_action") or "").strip().lower()
    if act == "git_status":
        return "git status (short, branch summary)"
    if act == "run_command":
        rn = (payload.get("run_name") or "").strip().lower()
        if rn in ALLOWED_RUN_COMMANDS:
            return " ".join(ALLOWED_RUN_COMMANDS[rn][:4]) + ("…" if len(ALLOWED_RUN_COMMANDS[rn]) > 4 else "")
        return rn or "—"
    if act == "file_read":
        return f"read file (relative: {(payload.get('relative_path') or '')[:120]})"
    if act == "file_write":
        return f"write file (relative: {(payload.get('relative_path') or '')[:120]})"
    if act == "list_directory":
        return f"list directory (relative: {(payload.get('relative_path') or '.')[:120]})"
    if act == "find_files":
        gg = ((payload.get("glob") or payload.get("pattern") or "*") or "")[:80]
        return f"find files glob={gg!r} under {(payload.get('relative_path') or '.')[:80]}"
    if act == "git_commit":
        return "git add -A && git commit (fixed message)"
    if act == "git_push":
        pr = (payload.get("push_remote") or "").strip()
        pf = (payload.get("push_ref") or "").strip()
        if pr and pf:
            return f"git push {pr} {pf}"
        if pr:
            return f"git push {pr}"
        return "git push"
    if act == "vercel_projects_list":
        return "vercel projects list"
    if act == "vercel_remove":
        pn = (payload.get("vercel_project_name") or payload.get("project_name") or "").strip()
        return f"vercel remove {pn} --yes" if pn else "vercel remove (needs project + vercel_yes)"
    if act == "read_multiple_files":
        return "read multiple text files under an allowed folder (no indexing)"
    if act == "chain":
        n = len(payload.get("actions") or []) if isinstance(payload.get("actions"), list) else 0
        return f"chain ({n} allowlisted steps)" if n else "chain"
    return act or "—"


def format_host_confirmation(payload: dict[str, Any], title: str) -> str:
    """Explicit offer before queueing (chat never runs tools directly)."""
    tool = allowed_tool_human(payload)
    act = (payload.get("host_action") or "").strip().lower() or "—"
    intel_intro = ""
    if payload.get("intel_analysis"):
        intel_intro = (
            "I can analyze files on demand — nothing runs in the background and nothing is indexed.\n\n"
            "This will read multiple files locally (read-only). "
            "Content is processed only for this answer (not stored).\n\n"
        )
    return intel_intro + (
        "I can run this locally through Nexa's host executor.\n\n"
        f"Action: {title}\n"
        "Approval: required\n"
        f"Allowed tool: {tool}\n"
        f"host_action: {act}\n\n"
        "Reply **run**, **yes**, **run it**, or **do it** to queue it."
    )


def format_queued_ack(title: str, job_id: int) -> str:
    return f"Queued local action: {title}. Job #{job_id} — awaiting approval."


def truncate_output_lines(text: str, *, max_lines: int = 14, max_chars: int = 3_500) -> str:
    t = (text or "").strip()
    if not t:
        return "(no output)"
    lines = t.splitlines()
    body = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        body += "\n…"
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + "\n…"
    return body


def format_host_completion_message(
    *,
    job_id: int,
    title: str,
    success: bool,
    body: str | None,
    err: str | None,
) -> str:
    """Readable block for chat / Telegram when a host job finishes."""
    status_w = "success" if success else "failure"
    head = (
        f"Local action completed: {title}\n"
        if success
        else f"Local action failed: {title}\n"
    )
    parts = [
        head.rstrip(),
        f"Job #{job_id}",
        f"Result: {status_w}",
    ]
    if success:
        parts.append("Output:")
        parts.append(truncate_output_lines(body or ""))
    else:
        parts.append("Error:")
        parts.append(truncate_output_lines(err or body or "Unknown error"))
    return "\n".join(parts)


def completion_system_event_text(title: str, success: bool) -> str:
    return (
        f"Local action completed: {title}"
        if success
        else f"Local action failed: {title}"
    )


def allowed_actions_catalog() -> list[str]:
    """Stable list for /host and System tab (no new actions)."""
    return [
        "git_status — repository status (short)",
        "run_command — pytest (allowlisted)",
        "file_read — read a relative file under the work root",
        "file_write — write a relative file under the work root",
        "list_directory — list entries under a relative directory",
        "find_files — glob match files under a relative directory",
        "git_commit — stage all and commit with a fixed message",
        "git_push — push commits to remote (optional push_remote / push_ref)",
        "vercel_projects_list — vercel projects list (read-only)",
        "vercel_remove — vercel remove <slug> --yes (requires vercel_yes: true)",
        "read_multiple_files — batch-read text files under a folder (optional LLM summary)",
        "chain — run multiple allowlisted host_action steps in order (flag-gated; one approval)",
    ]


def host_executor_panel_public() -> dict[str, Any]:
    """Safe JSON for web System tab (no secrets)."""
    s = get_settings()
    enabled = bool(getattr(s, "nexa_host_executor_enabled", False))
    timeout = min(max(int(getattr(s, "host_executor_timeout_seconds", 120)), 5), 3600)
    max_bytes = min(max(int(getattr(s, "host_executor_max_file_bytes", 262_144)), 1024), 2_000_000)
    runs = sorted(ALLOWED_RUN_COMMANDS.keys())
    return {
        "enabled": enabled,
        "work_root": _resolved_work_root(),
        "allowed_host_actions": [
            "git_status",
            "run_command",
            "file_read",
            "file_write",
            "git_commit",
            "git_push",
            "vercel_projects_list",
            "vercel_remove",
            "list_directory",
            "find_files",
            "read_multiple_files",
            "chain",
        ],
        "allowed_run_names": runs,
        "timeout_seconds": timeout,
        "max_file_bytes": max_bytes,
    }


def host_executor_public() -> dict[str, Any]:
    """Alias with a clear name for API responses."""
    return host_executor_panel_public()


def telegram_host_command_text() -> str:
    panel = host_executor_public()
    en = "enabled" if panel["enabled"] else "disabled"
    lines = [
        "Host executor",
        f"Status: {en} on this API server.",
        "",
        "Work root (worker): "
        + (panel["work_root"][:180] + ("…" if len(panel["work_root"]) > 180 else "")),
        "",
        "Allowed host_action values: "
        + ", ".join(panel["allowed_host_actions"]),
        "Allowed run_command names: " + ", ".join(panel["allowed_run_names"]),
        f"Timeout: {panel['timeout_seconds']}s · Max file bytes: {panel['max_file_bytes']}",
        "",
        "You can ask in chat (still requires job approval before run):",
        "• run tests",
        "• check git status",
        "• read file README.md",
        "• write file notes.txt with hello",
        "",
        "Jobs use allowlisted tools only — no arbitrary shell.",
    ]
    if not panel["enabled"]:
        lines.insert(
            3,
            "Chat queueing is disabled until NEXA_HOST_EXECUTOR_ENABLED=1 on the API.",
        )
    return "\n".join(lines)
