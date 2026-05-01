"""
Map natural phrases to host_executor payload_json shapes.

Only emits allowlisted structures — no raw shell, no arbitrary commands.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def safe_relative_path(raw: str) -> str | None:
    s = (raw or "").strip().strip('`"\'')
    if not s or len(s) > 240:
        return None
    rel = s.replace("\\", "/").lstrip("/")
    if not rel:
        return None
    parts = Path(rel).parts
    if ".." in parts:
        return None
    if not re.fullmatch(r"[a-zA-Z0-9_.\-/]+", rel):
        return None
    return rel


_RE_GIT = re.compile(
    r"(?i)(?:^|[\s,])(?:check|show)\s+git\s+status\b|\bgit\s+status\b"
)
_RE_READ = re.compile(
    r"(?i)^(read|show|cat|open)\s+(?:file\s+)?([\w.`'\"/\-.]{1,240})$"
)
_RE_WRITE = re.compile(
    r"(?i)^write\s+(?:to\s+)?(?:file\s+)?([\w.`'\"/\-.]{1,240})\s+(?:with|using|containing|:)\s*(.+)$",
    re.DOTALL,
)


def title_for_payload(payload: dict[str, Any]) -> str:
    """Short user-facing label for queued / approval UI."""
    act = (payload.get("host_action") or "").strip().lower()
    if act == "git_status":
        return "Git status"
    if act == "run_command":
        rn = (payload.get("run_name") or "").strip().lower()
        if rn == "pytest":
            return "Run tests (pytest)"
        return f"Run {rn}" if rn else "Run command"
    if act == "file_read":
        p = (payload.get("relative_path") or "").strip()
        return f"Read file {p}" if p else "Read file"
    if act == "file_write":
        p = (payload.get("relative_path") or "").strip()
        return f"Write file {p}" if p else "Write file"
    if act == "list_directory":
        p = (payload.get("relative_path") or ".").strip() or "."
        return f"List directory {p}"
    if act == "find_files":
        p = (payload.get("relative_path") or ".").strip() or "."
        g = (payload.get("glob") or payload.get("pattern") or "*").strip()
        return f"Find files ({g}) in {p}"
    if act == "git_commit":
        return "Git commit"
    if act == "read_multiple_files":
        if payload.get("relative_paths"):
            return "Read multiple files (compare/explicit)"
        p = (payload.get("relative_path") or payload.get("relative_dir") or ".").strip() or "."
        return f"Analyze folder {p}"
    return "Host action"


def infer_host_executor_action(user_text: str) -> dict[str, Any] | None:
    """
    If the line clearly requests a supported host tool, return payload_json fragment
    for host_action. Otherwise None.
    """
    t = (user_text or "").strip()
    if not t or len(t) > 2_000:
        return None
    line = t.splitlines()[0].strip()

    if _RE_WRITE.match(line):
        m = _RE_WRITE.match(line)
        assert m is not None
        path_raw, content = m.group(1), (m.group(2) or "").strip()
        rel = safe_relative_path(path_raw)
        if not rel or not content:
            return None
        return {"host_action": "file_write", "relative_path": rel, "content": content}

    wm = _RE_READ.match(line)
    if wm:
        rel = safe_relative_path(wm.group(2))
        if not rel:
            return None
        root = Path(get_settings().host_executor_work_root).expanduser().resolve()
        try:
            candidate = (root / rel).resolve()
            candidate.relative_to(root)
        except (OSError, ValueError):
            # Outside work root or invalid — let local_file_intent handle abs / permission paths
            return None
        if not candidate.exists():
            return None
        if candidate.is_dir():
            return None
        if candidate.is_file():
            return {"host_action": "file_read", "relative_path": rel}
        return None

    low = line.lower()
    if _RE_GIT.search(line):
        return {"host_action": "git_status"}

    if re.search(r"(?i)\brun\s+tests?\b|\brun\s+pytest\b|^pytest\b", low):
        return {"host_action": "run_command", "run_name": "pytest"}

    return None
