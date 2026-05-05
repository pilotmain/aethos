"""Synchronous security review for ``@qa_agent`` style sub-agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.services.skills.builtin.security_scanner import scan_security
from app.services.sub_agent_registry import SubAgent
from app.services.workspace_resolver import extract_path_hint_from_message, resolve_workspace_path


def format_security_report(results: dict[str, Any]) -> str:
    secrets = results.get("secrets") or []
    deps = results.get("dependencies") or []
    unsafe = results.get("unsafe_patterns") or []
    root = results.get("root") or ""

    total = len(secrets) + len(deps) + len(unsafe)
    if total == 0:
        return (
            "✅ **Security scan (heuristic)**\n\n"
            f"Root: `{root}`\n"
            "No high-signal pattern matches. Still run pip-audit / npm audit for CVEs."
        )

    lines = [
        "🔒 **Security scan (heuristic)**",
        "",
        f"Root: `{root}`",
        f"**Signals:** {total} (not all are vulnerabilities)",
        "",
    ]
    if secrets:
        lines.append("### Possible secrets / keys")
        for it in secrets[:12]:
            lines.append(f"- `{it['file']}` L{it['line']}: {it['issue']} ({it['severity']})")
        if len(secrets) > 12:
            lines.append(f"- … and {len(secrets) - 12} more")
        lines.append("")

    if unsafe:
        lines.append("### Unsafe patterns")
        for it in unsafe[:12]:
            lines.append(f"- `{it['file']}` L{it['line']}: {it['issue']} ({it['severity']})")
        if len(unsafe) > 12:
            lines.append(f"- … and {len(unsafe) - 12} more")
        lines.append("")

    if deps:
        lines.append("### Dependencies")
        for it in deps:
            lines.append(f"- {it.get('issue', 'note')}")
        lines.append("")

    lines.append("_Heuristic only — review findings before changing production secrets._")
    return "\n".join(lines)


def run_security_review_sync(
    agent: SubAgent,
    message: str,
    *,
    db: Session | None,
    user_id: str,
) -> str:
    """Resolve workspace, run static scan, return Markdown-ish report."""
    _ = agent  # reserved for future per-agent policy
    hint = extract_path_hint_from_message(message)
    try:
        root_path = resolve_workspace_path(hint, db=db, owner_user_id=user_id or None)
    except ValueError as exc:
        return f"❌ {exc}"
    if not Path(root_path).is_dir():
        return f"❌ Not a directory: {root_path}"
    results = scan_security(root_path)
    return format_security_report(results)


__all__ = ["format_security_report", "run_security_review_sync"]
