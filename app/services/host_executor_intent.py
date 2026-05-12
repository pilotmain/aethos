"""
Map natural phrases to host_executor payload_json shapes.

Only emits allowlisted structures — no raw shell, no arbitrary commands.
"""

from __future__ import annotations

import re
import shlex
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
_PATH_TOKEN = r"([\w.`'\"/\-.~]{1,400})"
_RE_CREATE_FILE_WITH_CONTENT = re.compile(
    rf"(?is)^(?:create|make)\s+(?:a\s+)?file\s+(?:called|named)?\s*{_PATH_TOKEN}\s+"
    rf"(?:with\s+content|with|that\s+(?:says|contains|reads))\s+(.+?)(?:\s+in\s+{_PATH_TOKEN})?\s*$"
)
_RE_WRITE_CONTENT_TO = re.compile(
    rf"(?is)^(?:write|save)\s+(.+?)\s+to\s+(?:file\s+)?{_PATH_TOKEN}\s*$"
)
_RE_WRITE = re.compile(
    r"(?i)^write\s+(?:to\s+)?(?:file\s+)?([\w.`'\"/\-.]{1,240})\s+(?:with|using|containing|:)\s*(.+)$",
    re.DOTALL,
)
_COMMAND_PATTERNS = [
    (r"^(?:run|execute)\s+(.+?)\s+in\s+([\w.`'\"/\-.~]{1,400})$", "run_command_with_dir"),
    (r"^npm\s+install\s+(.+?)$", "npm_install"),
    (r"^pip\s+install\s+(.+?)$", "pip_install"),
    (r"^install\s+(.+?)(?:\s+package)?$", "install_package"),
    (r"^start\s+(?:a|the)\s+(.+?)\s+server(?:\s+on\s+port\s+(\d{2,5}))?$", "start_server"),
    (r"^clone\s+(https?://[^\s]+|git@[^\s]+)$", "git_clone"),
    (r"^create\s+directory\s+(.+?)$", "create_directory"),
    (r"^mkdir\s+(.+?)$", "create_directory"),
    (r"^create\s+(?:a\s+)?react\s+app\s+called\s+([\w.-]{1,80})(?:\s+and\s+start\s+it)?$", "create_react_app"),
    (r"^(?:run|execute)\s+(.+?)$", "run_command"),
]


def _strip_outer_quotes(raw: str) -> str:
    s = (raw or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in {"'", '"', "`"}:
        return s[1:-1].strip()
    return s


def _clean_path_token(raw: str) -> str:
    return (raw or "").strip().strip('`"\'').rstrip(".,;")


def _write_target_relative_path(path_raw: str, *, parent_raw: str | None = None) -> str | None:
    """Normalize relative paths, or absolute paths that are inside the host work root."""
    raw_path = _clean_path_token(path_raw)
    raw_parent = _clean_path_token(parent_raw or "")
    if not raw_path:
        return None

    target = Path(raw_path)
    if raw_parent and not target.is_absolute():
        target = Path(raw_parent) / raw_path

    target_text = str(target).strip()
    if target.is_absolute() or target_text.startswith("~"):
        try:
            root = Path(get_settings().host_executor_work_root).expanduser().resolve()
            candidate = Path(target_text).expanduser().resolve()
            rel = candidate.relative_to(root)
        except (OSError, ValueError):
            return None
        return safe_relative_path(str(rel).replace("\\", "/"))

    return safe_relative_path(target_text.replace("\\", "/"))


def title_for_payload(payload: dict[str, Any]) -> str:
    """Short user-facing label for queued / approval UI."""
    act = (payload.get("host_action") or "").strip().lower()
    if act == "git_status":
        return "Git status"
    if act == "run_command":
        cmd = (payload.get("command") or "").strip()
        if cmd:
            preview = cmd[:80] + ("..." if len(cmd) > 80 else "")
            return f"Run command: {preview}"
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
    if act == "git_push":
        return "Git push"
    if act == "vercel_projects_list":
        return "Vercel projects list"
    if act == "vercel_remove":
        pn = (payload.get("vercel_project_name") or payload.get("project_name") or "").strip()
        return f"Vercel remove {pn}" if pn else "Vercel remove project"
    if act == "read_multiple_files":
        if payload.get("relative_paths"):
            return "Read multiple files (compare/explicit)"
        p = (payload.get("relative_path") or payload.get("relative_dir") or ".").strip() or "."
        return f"Analyze folder {p}"
    if act == "chain":
        n = len(payload.get("actions") or []) if isinstance(payload.get("actions"), list) else 0
        return f"Host action chain ({n} steps)" if n else "Host action chain"
    if act == "plugin_skill":
        sn = (payload.get("skill_name") or "").strip()
        return f"Plugin skill ({sn})" if sn else "Plugin skill"
    return "Host action"


def parse_file_write_intent(text: str) -> dict[str, Any] | None:
    """
    Parse natural-language file write phrasing into display-friendly parts.

    This is detection only. Execution still goes through ``infer_host_executor_action``
    so paths are normalized under ``HOST_EXECUTOR_WORK_ROOT`` before queueing.
    """
    if not text or not isinstance(text, str):
        return None
    line = text.strip().splitlines()[0].strip()
    if not line:
        return None

    # Shorthand: "make a file notes.txt says Hello world" (bare ``says``, not only ``that says``).
    m_says = re.match(
        r"(?is)^(?:make|create)\s+(?:a\s+)?file\s+(\S+)\s+says\s+(.+)$",
        line,
    )
    if m_says:
        filename = _clean_path_token(m_says.group(1))
        content = _strip_outer_quotes((m_says.group(2) or "").strip())
        if filename and content:
            return {"filename": filename, "content": content, "directory": None}

    match = _RE_WRITE.match(line)
    if match:
        filename = _clean_path_token(match.group(1))
        content = _strip_outer_quotes((match.group(2) or "").strip())
        if not filename or not content:
            return None
        return {"filename": filename, "content": content, "directory": None}

    match = _RE_CREATE_FILE_WITH_CONTENT.match(line)
    if match:
        filename = _clean_path_token(match.group(1))
        content = _strip_outer_quotes((match.group(2) or "").strip())
        directory = _clean_path_token(match.group(3) or "") if match.lastindex and match.lastindex >= 3 else ""
        if not filename or not content:
            return None
        return {"filename": filename, "content": content, "directory": directory or None}

    match = _RE_WRITE_CONTENT_TO.match(line)
    if match:
        filename = _clean_path_token(match.group(2))
        content = _strip_outer_quotes((match.group(1) or "").strip())
        if not filename or not content:
            return None
        return {"filename": filename, "content": content, "directory": None}

    return None


def _quote_command_arg(raw: str) -> str:
    return shlex.quote((raw or "").strip())


def _command_from_intent(intent_type: str, match: re.Match[str]) -> tuple[str, str | None]:
    first = (match.group(1) or "").strip()
    cwd = None
    if intent_type == "run_command_with_dir":
        cwd = (match.group(2) or "").strip()
        return first, cwd
    if intent_type == "run_command":
        return first, None
    if intent_type == "npm_install":
        return f"npm install {_quote_command_arg(first)}", None
    if intent_type == "pip_install":
        return f"pip install {_quote_command_arg(first)}", None
    if intent_type == "install_package":
        return f"npm install {_quote_command_arg(first)}", None
    if intent_type == "git_clone":
        return f"git clone {_quote_command_arg(first)}", None
    if intent_type == "create_directory":
        return f"mkdir -p {_quote_command_arg(first)}", None
    if intent_type == "create_react_app":
        return f"npx create-react-app {_quote_command_arg(first)}", None
    if intent_type == "start_server":
        server = first.lower()
        port = (match.group(2) or "").strip() if match.lastindex and match.lastindex >= 2 else ""
        if "web" in server and port:
            return f"python3 -m http.server {port}", None
        if "dev" in server:
            return "npm run dev", None
        return "npm start", None
    return first, None


_STATUS_PATTERNS: list[tuple[str, str]] = [
    (r"^(?:what\'s|what is)\s+(?:the\s+)?(?:status|progress)$", "get_status"),
    (r"^(?:show|list)\s+(?:my\s+)?(?:tasks|work|progress)$", "list_tasks"),
    (r"^(?:what|who)\s+is\s+working(?:\s+on\s+what)?$", "active_work"),
    (r"^(?:who\'s|who is)\s+working\b", "active_work"),
    (r"^who\s+is\s+working\b", "active_work"),
    (r"^(?:any\s+)?(?:update|report|heartbeat)$", "heartbeat"),
]


def parse_status_intent(text: str) -> dict[str, Any] | None:
    """Parse status / dashboard inquiry intent."""
    if not text or not isinstance(text, str):
        return None
    text_lower = text.strip().splitlines()[0].strip().lower()
    if not text_lower:
        return None
    for pattern, intent_type in _STATUS_PATTERNS:
        if re.search(pattern, text_lower):
            return {"intent": intent_type}
    return None


_READ_NL_PATTERNS: list[tuple[str, str]] = [
    (r"^(?:read|show|cat|open)\s+(?:file\s+)?(.+)$", "read_file"),
    (r"^(?:what\'s|what is|show me)\s+in\s+(.+)$", "read_file"),
]


def parse_read_intent(text: str) -> dict[str, Any] | None:
    """Parse natural-language read-file intent (paths resolved under command workspace root)."""
    if not text or not isinstance(text, str):
        return None
    line = text.strip().splitlines()[0].strip()
    if not line:
        return None
    # Avoid treating "show me system status" as `show <path>` → path "me system status".
    from app.services.observability.runtime_store import parse_observability_intent

    if parse_observability_intent(line):
        return None
    text_lower = line.lower()
    for pattern, _kind in _READ_NL_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            fp = (match.group(1) or "").strip().strip(",.;")
            if not fp:
                return None
            return {"intent": "read_file", "filepath": fp, "raw_text": text}
    return None


def parse_command_intent(text: str) -> dict[str, Any] | None:
    """Parse natural language command intent."""
    if not text or not isinstance(text, str):
        return None
    line = text.strip().splitlines()[0].strip()
    if not line:
        return None

    for pattern, intent_type in _COMMAND_PATTERNS:
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            command, cwd = _command_from_intent(intent_type, match)
            if not command:
                return None
            out: dict[str, Any] = {
                "intent": "command_execution",
                "command_type": intent_type,
                "command": command,
                "raw_text": text,
            }
            if cwd:
                out["directory"] = cwd
            return out
    return None


def infer_host_executor_action(user_text: str) -> dict[str, Any] | None:
    """
    If the line clearly requests a supported host tool, return payload_json fragment
    for host_action. Otherwise None.
    """
    t = (user_text or "").strip()
    if not t or len(t) > 2_000:
        return None
    line = t.splitlines()[0].strip()

    write_intent = parse_file_write_intent(line)
    if write_intent:
        parent_raw = write_intent.get("directory")
        rel = _write_target_relative_path(
            str(write_intent.get("filename") or ""),
            parent_raw=str(parent_raw) if parent_raw else None,
        )
        content = str(write_intent.get("content") or "")
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

    command_intent = parse_command_intent(line)
    if command_intent:
        from app.services.host_executor import is_command_safe

        command = str(command_intent.get("command") or "").strip()
        if not is_command_safe(command):
            return None
        out = {
            "host_action": "run_command",
            "command": command,
            "command_type": str(command_intent.get("command_type") or "").strip(),
        }
        directory = str(command_intent.get("directory") or "").strip()
        if directory:
            cwd_rel = _write_target_relative_path(".", parent_raw=directory)
            if not cwd_rel:
                return None
            out["cwd_relative"] = "." if cwd_rel == "." else cwd_rel.rstrip("/")
        return out

    if re.search(r"(?i)(?:^|[\s,])\bgit\s+push\b", line):
        return {"host_action": "git_push"}

    if re.search(
        r"(?i)\b(list|show)\s+(my\s+)?vercel\s+projects\b|\bvercel\s+projects\s+list\b",
        line,
    ):
        return {"host_action": "vercel_projects_list"}

    return None


def parse_deploy_intent(text: str) -> dict[str, Any] | None:
    """
    Detect generic deploy phrases (gateway NL → :mod:`app.services.deployment`).

    ``deploy_type`` is ``deploy_preview`` for preview installs (non-production Vercel / Netlify smoke URLs).
    """
    if not text or not isinstance(text, str):
        return None
    line = text.strip().splitlines()[0].strip()
    if not line:
        return None

    low = line.lower()

    m = re.match(r"(?is)^preview\s+deploy(?:\s+to\s+([\w.-]+))?\s*$", line)
    if m:
        prov = (m.group(1) or "").strip() or None
        return {
            "intent": "deploy",
            "deploy_type": "deploy_preview",
            "provider": prov,
            "raw_text": text,
        }

    if re.match(r"(?is)^deploy\s+preview\s*$", low):
        return {
            "intent": "deploy",
            "deploy_type": "deploy_preview",
            "provider": None,
            "raw_text": text,
        }

    m = re.match(r"(?is)^deploy\s+to\s+([\w.-]+)\s*$", line)
    if m:
        return {
            "intent": "deploy",
            "deploy_type": "deploy",
            "provider": m.group(1).strip(),
            "raw_text": text,
        }

    m = re.match(r"(?is)^deploy\s+([\w.-]+)\s+to\s+production\s*$", low)
    if m:
        return {
            "intent": "deploy",
            "deploy_type": "deploy",
            "provider": m.group(1).strip(),
            "raw_text": text,
        }

    if re.match(r"(?is)^deploy(?:\s+this)?(?:\s+project)?\s*$", line):
        return {"intent": "deploy", "deploy_type": "deploy", "provider": None, "raw_text": text}

    if re.match(r"(?is)^push\s+to\s+production\s*$", low):
        return {"intent": "deploy", "deploy_type": "deploy", "provider": None, "raw_text": text}

    if re.match(r"(?is)^go\s+live\s*$", low):
        return {"intent": "deploy", "deploy_type": "deploy", "provider": None, "raw_text": text}

    m = re.match(r"(?is)^publish\s+([\w.-]+)\s*$", low)
    if m:
        return {
            "intent": "deploy",
            "deploy_type": "deploy",
            "provider": m.group(1).strip(),
            "raw_text": text,
        }

    return None


def parse_deploy_from_intent(text: str) -> dict[str, Any] | None:
    """
    ``deploy from <path>`` / ``deploy this folder <path>`` — set project root then run deploy flow.

    Path is first-line only; strip wrapping quotes/backticks.
    """
    if not text or not isinstance(text, str):
        return None
    line = text.strip().splitlines()[0].strip()
    if not line:
        return None

    m = re.match(r"(?is)^deploy\s+from\s+(.+)$", line)
    if m:
        return {"intent": "set_deploy_root_and_deploy", "folder": m.group(1).strip(), "raw_text": text}

    m2 = re.match(r"(?is)^deploy\s+this\s+folder\s+(.+)$", line)
    if m2:
        return {"intent": "set_deploy_root_and_deploy", "folder": m2.group(1).strip(), "raw_text": text}

    m3 = re.match(r"(?is)^deploy\s+folder\s+(.+)$", line)
    if m3:
        return {"intent": "set_deploy_root_and_deploy", "folder": m3.group(1).strip(), "raw_text": text}

    return None


def parse_deploy_root_intent(text: str) -> dict[str, Any] | None:
    """
    Change deploy directory while a cloud choice is pending (e.g. ``change deploy root to /path``).
    """
    if not text or not isinstance(text, str):
        return None
    line = text.strip().splitlines()[0].strip()
    if not line:
        return None

    patterns = (
        r"(?is)^(?:change|set)\s+deploy\s+root\s+to\s+(.+)$",
        r"(?is)^use\s+deploy\s+root\s+(.+)$",
        r"(?is)^deploy\s+root\s+to\s+(.+)$",
        r"(?is)^deploy\s+from\s+folder\s+(.+)$",
    )
    for pat in patterns:
        m = re.match(pat, line)
        if m:
            return {"intent": "change_deploy_root", "folder": m.group(1).strip(), "raw_text": text}
    return None


def parse_deployment_status_intent(text: str) -> dict[str, Any] | None:
    """NL intent to list cloud projects / deployments (gateway deployment-status hook)."""
    if not text or not isinstance(text, str):
        return None
    line = text.strip().splitlines()[0].strip()
    if not line:
        return None
    low = line.lower()

    if re.search(r"(?i)^(?:check|list)\s+(?:my\s+)?vercel\s+(?:projects|deployments|services)\s*$", low):
        return {"intent": "check_deployments", "provider": "vercel", "raw_text": text}
    if re.search(r"(?i)^(?:check|list)\s+(?:my\s+)?railway\s+(?:projects|deployments|services)\s*$", low):
        return {"intent": "check_deployments", "provider": "railway", "raw_text": text}

    m = re.search(r"(?i)\bwhat(?:'s| is)\s+(?:running|deployed)\s+on\s+(vercel|railway)\b", low)
    if m:
        return {"intent": "check_deployments", "provider": m.group(1).lower(), "raw_text": text}

    m_lm = re.search(r"(?i)\blist\s+my\s+(vercel|railway)\s+projects\b", low)
    if m_lm:
        return {"intent": "check_deployments", "provider": m_lm.group(1).lower(), "raw_text": text}

    m_show = re.search(r"(?i)^(?:show\s+)?(?:my\s+)?(vercel|railway)\s+(?:projects|deployments)\s*$", low)
    if m_show:
        return {"intent": "check_deployments", "provider": m_show.group(1).lower(), "raw_text": text}

    return None


def is_cancel_deploy_intent(text: str) -> bool:
    """User wants to abandon an in-progress deploy cloud-choice prompt."""
    if not text or not isinstance(text, str):
        return False
    line = text.strip().splitlines()[0].strip().lower()
    if not line:
        return False
    patterns = (
        r"^(cancel|stop|abort|exit|quit|skip|nope|forget\s+it|nevermind|never\s+mind)\s*$",
        r"^no\s*$",
        r"^cancel\s+(?:that|this|deploy|deployment)\s*$",
        r"^(?:don'?t|do\s+not)\s+deploy\s*$",
    )
    return any(re.match(p, line) for p in patterns)


def is_reset_deploy_intent(text: str) -> bool:
    """Clear saved deploy-choice state without starting a deploy."""
    if not text or not isinstance(text, str):
        return False
    line = text.strip().splitlines()[0].strip().lower()
    if not line:
        return False
    patterns = (
        r"^reset\s+deploy\s*$",
        r"^clear\s+deploy\s+state\s*$",
        r"^clear\s+deployment\s+state\s*$",
    )
    return any(re.match(p, line) for p in patterns)


def parse_available_clouds_intent(text: str) -> bool:
    """User is asking which deployment CLIs / targets exist on this machine."""
    if not text or not isinstance(text, str):
        return False
    line = text.strip().splitlines()[0].strip().lower()
    if not line:
        return False
    if parse_deploy_intent(text):
        return False
    patterns = (
        r"\bwhat\s+clouds?\b",
        r"\bwhat\s+(?:deployment|deploy)\s+(?:options|targets|providers)\b",
        r"\bwhere\s+can\s+i\s+deploy\b",
        r"\bavailable\s+clouds\b",
        r"\bwhich\s+clouds?\b",
        r"\blist\s+(?:my\s+)?deployment\s+(?:tools|clis|targets)\b",
        r"\bwhat\s+can\s+i\s+deploy\s+to\b",
    )
    return any(re.search(p, line) for p in patterns)
