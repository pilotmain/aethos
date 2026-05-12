# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""User-facing release notes (CHANGELOG.md) for Nexa — no secrets, no commit dumps."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

_DATE_TITLE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_HEADER = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_changelog_path() -> Path:
    return _repo_root() / "CHANGELOG.md"


def get_release_updates(changelog_path: Path | None = None) -> str:
    """Return full CHANGELOG text, or empty string if the file is missing or unreadable."""
    path = changelog_path or _default_changelog_path()
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _split_markdown_sections(text: str) -> list[tuple[str, str]]:
    """Split on `## title` lines; returns (header_title, body) pairs, in file order."""
    if not text.strip():
        return []
    lines = text.splitlines()
    sections: list[tuple[str, str]] = []
    cur_title: str | None = None
    cur_body: list[str] = []
    for line in lines:
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if cur_title is not None:
                sections.append((cur_title, "\n".join(cur_body).strip()))
            cur_title = m.group(1).strip()
            cur_body = []
        elif cur_title is not None:
            cur_body.append(line)
    if cur_title is not None:
        sections.append((cur_title, "\n".join(cur_body).strip()))
    return sections


def _parse_version_tuple(title: str) -> tuple[int, ...] | None:
    m = re.match(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$", title.strip(), re.IGNORECASE)
    if not m:
        return None
    parts = [int(m.group(1)), int(m.group(2))]
    if m.group(3) is not None:
        parts.append(int(m.group(3)))
    return tuple(parts)


def _version_release_id(title: str) -> str:
    t = title.strip()
    if t.lower().startswith("v"):
        return t
    return f"v{t}"


def _fallback_release_id(body: str) -> str:
    raw = "\n".join(line.rstrip() for line in body.splitlines()).strip()
    if not raw:
        return ""
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"h-{digest}"


def _legacy_split_dated_bodies(changelog: str) -> list[tuple[str, str]]:
    """Files with only `## YYYY-MM-DD` and no other ## sections."""
    if not changelog.strip():
        return []
    matches = list(_DATE_HEADER.finditer(changelog))
    if not matches:
        return []
    out: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        d = m.group(1)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(changelog)
        body = changelog[m.end() : end].strip()
        out.append((d, body))
    return out


def resolve_latest_release(changelog_path: Path | None = None) -> tuple[str, str, str]:
    """
    Returns (release_id, section_body, raw_section_markdown).

    Prefers newest ISO date section, else highest semver `## vX.Y`, else legacy dated-only
    parse, else hash of first non-Unreleased section with content.
    """
    text = get_release_updates(changelog_path)
    sections = _split_markdown_sections(text)
    pairs = [(t.strip(), b) for t, b in sections if t.strip().lower() != "unreleased"]

    dated = [(t, b) for t, b in pairs if _DATE_TITLE.match(t)]
    if dated:
        t, b = max(dated, key=lambda x: x[0])
        return (t, b, f"## {t}\n\n{b}".strip())

    ver = [(t, b) for t, b in pairs if _parse_version_tuple(t)]
    if ver:
        t, b = max(ver, key=lambda x: _parse_version_tuple(x[0]) or ())
        rid = _version_release_id(t)
        return (rid, b, f"## {t}\n\n{b}".strip())

    legacy = _legacy_split_dated_bodies(text)
    if legacy:
        legacy.sort(key=lambda p: p[0], reverse=True)
        d, body = legacy[0]
        raw = f"## {d}\n\n{body}".strip()
        return (d, body, raw)

    for t, b in pairs:
        if b.strip():
            rid = _fallback_release_id(b)
            return (rid, b, f"## {t}\n\n{b}".strip())

    return ("", "", "")


def get_current_release_id(changelog_path: Path | None = None) -> str:
    """Stable identity for localStorage (ISO date, v0.x, or h-<hash>)."""
    rid, _body, _raw = resolve_latest_release(changelog_path)
    return rid


def _strip_markdown_noise(line: str) -> str:
    s = line.strip()
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"__(.+?)__", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return s.strip()


def _raw_section_bullets(body: str, limit: int = 24) -> list[str]:
    take: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        m = re.match(r"^[\*\-•]\s+(.+)$", s)
        if m:
            item = _strip_markdown_noise(m.group(1))
            if item and "(work in progress" not in item.lower():
                take.append(item)
        if len(take) >= limit:
            break
    return take


def get_latest_release_summary(changelog_path: Path | None = None) -> list[str]:
    """3–6 short bullet strings from the latest section (fewer if the file lists fewer)."""
    _rid, body, _raw = resolve_latest_release(changelog_path)
    if not body.strip():
        return []
    bullets = _raw_section_bullets(body, limit=24)
    if not bullets:
        return []
    return bullets[:6]


def get_release_latest_for_web(changelog_path: Path | None = None) -> dict[str, Any]:
    """Single resolve for GET /web/release/latest (release_id, summary bullets, section markdown)."""
    rid, body, raw = resolve_latest_release(changelog_path)
    items = _raw_section_bullets(body, limit=24)[:6]
    return {
        "release_id": rid,
        "items": items,
        "full_text": (raw[:50_000] if raw else ""),
    }


def get_latest_release_update(changelog_path: Path | None = None) -> dict[str, Any]:
    """Full bullet list for Telegram / legacy release-notes API."""
    rid, body, raw_section = resolve_latest_release(changelog_path)
    if not rid and not body:
        return {
            "release_id": "",
            "date_label": "",
            "raw_section": "",
            "headline": "Nexa",
            "bullets": [],
        }
    bullets = _raw_section_bullets(body, limit=20)
    date_label = rid if _DATE_TITLE.match(rid) else ""
    return {
        "release_id": rid,
        "date_label": date_label,
        "raw_section": raw_section,
        "headline": f"Nexa · {rid}" if rid else "Nexa",
        "bullets": bullets,
    }


def format_release_updates_for_chat() -> str:
    """Plain text for Telegram /updates."""
    lines = ["Nexa Updates", "", "Latest:"]
    summary = get_latest_release_summary()
    for b in summary[:8]:
        lines.append(f"• {b}")
    if not summary:
        lines.append("• (Release notes will appear when CHANGELOG is available on the host.)")
    lines.extend(["", "See CHANGELOG.md for full history."])
    return "\n".join(lines)
