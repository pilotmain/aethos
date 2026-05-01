"""Lightweight markdown shells for client-ready exports (no LLM)."""

from __future__ import annotations

from datetime import date


def _header_lines(title: str) -> list[str]:
    t = (title or "Document").strip() or "Document"
    return [f"# {t}", f"**Date:** {date.today().isoformat()}", ""]


def format_report_markdown(body: str, title: str = "Report") -> str:
    lines = _header_lines(title)
    lines += ["## Summary", "", (body or "").strip(), ""]
    return "\n".join(lines)


def format_research_brief(body: str, title: str = "Research brief") -> str:
    lines = _header_lines(title)
    lines += [
        "## Findings",
        "",
        (body or "").strip(),
        "",
        "## Notes",
        "",
        "_Sources and verification: add as needed._",
        "",
    ]
    return "\n".join(lines)


def format_project_plan(body: str, title: str = "Project plan") -> str:
    lines = _header_lines(title)
    lines += [
        "## Plan",
        "",
        (body or "").strip(),
        "",
        "## Next steps",
        "",
        "1. ",
        "",
    ]
    return "\n".join(lines)


def format_proposal(body: str, title: str = "Proposal") -> str:
    lines = _header_lines(title)
    lines += [
        "## Context",
        "",
        (body or "").strip(),
        "",
        "## Proposal",
        "",
        "_Scope, timeline, and success criteria to be agreed._",
        "",
    ]
    return "\n".join(lines)


def format_meeting_notes(body: str, title: str = "Meeting notes") -> str:
    lines = _header_lines(title)
    lines += [
        "## Attendees",
        "",
        "_Add names_",
        "",
        "## Notes",
        "",
        (body or "").strip(),
        "",
        "## Action items",
        "",
        "- ",
        "",
    ]
    return "\n".join(lines)
