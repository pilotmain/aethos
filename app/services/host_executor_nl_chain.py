"""
Narrow natural-language → ``host_action: chain`` (README + commit + push).

Gated by ``nexa_nl_to_chain_enabled`` and ``nexa_host_executor_chain_enabled``.
Same approval and validation path as a manual chain JSON payload.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.config import get_settings

_MAX_USER_TEXT = 4_000
_MAX_README_BYTES = 1_000_000
_DEFAULT_LINE = "Service updated via Nexa."


def _settings_allow_nl_chain() -> bool:
    s = get_settings()
    if not bool(getattr(s, "nexa_nl_to_chain_enabled", False)):
        return False
    if not bool(getattr(s, "nexa_host_executor_enabled", False)):
        return False
    if not bool(getattr(s, "nexa_host_executor_chain_enabled", False)):
        return False
    return True


def _strip_commit_forbidden(msg: str) -> str:
    m = (msg or "").strip()
    if re.search(r"[`$;|&]", m):
        m = re.sub(r"[`$;|&]", "", m)
    return m.strip() or "docs: update readme"


def _commit_message_from_readme_body(body: str) -> str:
    raw = (body or "").strip()
    first = raw.splitlines()[0].strip() if raw else ""
    first = re.sub(r"^#+\s*", "", first).strip()
    if not first:
        base = "update readme"
    else:
        base = first[:200]
    msg = f"docs: {base}"[:240]
    return _strip_commit_forbidden(msg)


def _format_readme_markdown(user_title: str) -> str:
    t = (user_title or "").strip()
    if not t:
        return f"# Update\n\n{_DEFAULT_LINE}"
    if t.startswith("#"):
        return t[:_MAX_README_BYTES]
    return f"# {t}\n\n{_DEFAULT_LINE}"[:_MAX_README_BYTES]


def _extract_title_for_readme(text: str) -> str | None:
    m = re.search(r'\bsaying\s+["\']([^"\']{1,1500})["\']', text, re.I)
    if m:
        return m.group(1).strip()
    m2 = re.search(r'\bwith\s+content\s+["\']([^"\']{1,1500})["\']', text, re.I)
    if m2:
        return m2.group(1).strip()
    m3 = re.search(
        r"\b(?:titled|title)\s+[\"']([^\"']{1,500})[\"']",
        text,
        re.I,
    )
    if m3:
        return m3.group(1).strip()
    return None


def try_infer_readme_push_chain_nl(user_text: str) -> dict[str, Any] | None:
    """
    If ``user_text`` matches a narrow "add/create/write README … push" pattern, return a chain payload.

    Otherwise return None (caller continues with other host inference).
    """
    if not _settings_allow_nl_chain():
        return None

    t = (user_text or "").strip()
    if not t or len(t) > _MAX_USER_TEXT:
        return None

    # Let explicit JSON host payloads use the normal paste / validation path.
    tl = t.lstrip()
    if tl.startswith("{") and '"host_action"' in t:
        return None

    low = t.lower()
    if not re.search(r"\b(add|create|write|update)\s+(a\s+)?readme\b", low):
        return None
    if not re.search(r"\bpush\b", low):
        return None

    title = _extract_title_for_readme(t)
    body = _format_readme_markdown(title) if title else _format_readme_markdown("")
    cm = _commit_message_from_readme_body(body)

    return {
        "host_action": "chain",
        "actions": [
            {"host_action": "file_write", "relative_path": "README.md", "content": body},
            {"host_action": "git_commit", "commit_message": cm},
            {"host_action": "git_push"},
        ],
        "stop_on_failure": True,
    }
