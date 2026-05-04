"""
Narrow natural-language → ``host_action: chain`` (README + commit + push).

Gated by ``nexa_nl_to_chain_enabled`` and ``nexa_host_executor_chain_enabled``.
Same approval and validation path as a manual chain JSON payload.

Optional repo folder hints: ``in <slug>``, ``under <slug>``, ``for <slug> repo``, ``to <slug>``,
explicit ``<slug>/README.md``, etc. Slugs are validated with :func:`~app.services.host_executor_intent.safe_relative_path`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.host_executor_intent import safe_relative_path

_MAX_USER_TEXT = 4_000
_MAX_README_BYTES = 1_000_000
_DEFAULT_LINE = "Service updated via Nexa."

# Skip bogus single-token “slugs” from prose.
_SLUG_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "my",
        "your",
        "this",
        "that",
        "repo",
        "readme",
        "git",
        "remote",
        "origin",
    }
)

_SLUG_SEGMENT = r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,120}"


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


def _normalize_slug_candidate(raw: str) -> str | None:
    """Single path segment under work root; no traversal; alphanumeric + ._-"""
    s = (raw or "").strip().strip('`"\'')
    if not s or s.lower() in _SLUG_STOPWORDS:
        return None
    sp = safe_relative_path(s)
    if not sp or "/" in sp:
        return None
    parts = Path(sp).parts
    if len(parts) != 1:
        return None
    seg = parts[0]
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,120}", seg):
        return None
    return seg


def extract_repo_path_and_cwd(user_text: str) -> tuple[str, str | None]:
    """
    Return ``(file_write relative_path, cwd_relative or None)``.

    Default when no safe hint: ``("README.md", None)``.
    """
    t = user_text or ""

    # 1) Explicit relative path …/README.md
    for rx in (
        rf"\b({_SLUG_SEGMENT}/README\.md)\b",
        rf"\b({_SLUG_SEGMENT}/readme\.md)\b",
    ):
        m = re.search(rx, t, re.I)
        if m:
            if m.start() >= 3 and t[m.start() - 3 : m.start()] == "../":
                continue
            full = safe_relative_path(m.group(1))
            if full:
                parts = Path(full).parts
                if len(parts) >= 2 and ".." not in parts:
                    return full, parts[0]

    # 2) slug/README (no extension)
    m = re.search(rf"\b({_SLUG_SEGMENT}/README)\b(?!\.\w)", t, re.I)
    if m:
        cand = m.group(1)
        slug_part = cand.split("/", 1)[0]
        slug = _normalize_slug_candidate(slug_part)
        if slug:
            rel = safe_relative_path(f"{slug}/README.md")
            if rel:
                return rel, slug

    # 3) Phrase-based slug (first match wins; ordered from most specific)
    slug_patterns = (
        rf"\bfor\s+({_SLUG_SEGMENT})\s+repo\b",
        rf"\bunder\s+({_SLUG_SEGMENT})\b",
        rf"\bto\s+({_SLUG_SEGMENT})\b",
        rf"\bin\s+({_SLUG_SEGMENT})\b",
    )
    for rx in slug_patterns:
        m = re.search(rx, t, re.I)
        if m:
            slug_raw_end = m.end(1)
            if slug_raw_end < len(t) and t[slug_raw_end] == "@":
                continue
            slug = _normalize_slug_candidate(m.group(1))
            if slug:
                rel = safe_relative_path(f"{slug}/README.md")
                if rel:
                    return rel, slug

    return "README.md", None


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

    rel_path, cwd_rel = extract_repo_path_and_cwd(t)

    title = _extract_title_for_readme(t)
    body = _format_readme_markdown(title) if title else _format_readme_markdown("")
    cm = _commit_message_from_readme_body(body)

    actions: list[dict[str, Any]] = [
        {"host_action": "file_write", "relative_path": rel_path, "content": body},
    ]
    gc: dict[str, Any] = {"host_action": "git_commit", "commit_message": cm}
    gp: dict[str, Any] = {"host_action": "git_push"}
    if cwd_rel:
        gc["cwd_relative"] = cwd_rel
        gp["cwd_relative"] = cwd_rel
    actions.extend([gc, gp])

    return {
        "host_action": "chain",
        "actions": actions,
        "stop_on_failure": True,
    }
