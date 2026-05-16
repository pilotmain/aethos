# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deterministic natural-language provider / deploy intents (Phase 2 Step 5)."""

from __future__ import annotations

import re
from typing import Any

from app.deploy_context.nl_resolution import (
    extract_project_slug_from_phrase,
    match_known_project_in_tokens,
    parse_environment_from_text,
)

# Intents routed to provider action layer (Vercel first).
_PROVIDER_PROJECT_INTENTS = frozenset(
    {
        "provider_restart",
        "provider_redeploy",
        "provider_deploy",
        "provider_status",
        "provider_logs",
        "provider_inspect",
    }
)

_RESTART = re.compile(
    r"(?is)^(?:please\s+)?restart\s+(?:the\s+)?(?:project\s+)?(?P<project>.+?)(?:\s+on\s+vercel)?\s*\.?\s*$"
)
_REDEPLOY = re.compile(
    r"(?is)^(?:please\s+)?(?:fix\s+and\s+)?redeploy\s+(?:the\s+)?(?:project\s+)?(?P<project>.+?)(?:\s+on\s+vercel)?\s*\.?\s*$"
)
_DEPLOY_PROJECT = re.compile(
    r"(?is)^(?:please\s+)?deploy\s+(?:the\s+)?(?:project\s+)?(?P<project>[\w][\w\s.-]{1,80}?)(?:\s+to\s+vercel)?\s*\.?\s*$"
)
_STATUS = re.compile(
    r"(?is)^(?:check|what(?:'s|\s+is|\s+happened\s+to)|how\s+is)\s+"
    r"(?:the\s+)?(?:deployment\s+(?:for|of)\s+)?(?P<project>[\w][\w\s.-]{1,80}?)"
    r"(?:\s+'s)?\s+(?:production|deployment|live)(?:\s+status)?\s*\.?\s*$"
)
_IS_LIVE = re.compile(
    r"(?is)^(?:is\s+)?(?P<project>[\w][\w\s.-]{1,80}?)\s+(?:live|up|deployed)(?:\s+on\s+vercel)?\s*\.?\s*$"
)
_LOGS = re.compile(
    r"(?is)^(?:show|get|open|tail)\s+(?:(?:the\s+)?(?P<project>[\w][\w\s.-]{1,80}?)\s+)?"
    r"(?:deployment\s+)?logs(?:\s+for\s+(?P<project2>[\w][\w\s.-]{1,80}?))?\s*\.?\s*$"
)
_INSPECT = re.compile(
    r"(?is)^(?:inspect|show)\s+(?:vercel\s+)?(?:project\s+)?(?P<project>[\w][\w\s.-]{1,80}?)\s*\.?\s*$"
)
_SCAN_PROVIDERS = re.compile(r"(?is)^(?:aethos\s+)?(?:providers?\s+scan|scan\s+providers?)\s*\.?\s*$")
_SCAN_PROJECTS = re.compile(r"(?is)^(?:aethos\s+)?(?:projects?\s+scan|scan\s+(?:local\s+)?projects?)\s*\.?\s*$")
_LINK = re.compile(
    r"(?is)^(?:aethos\s+)?(?:projects?\s+)?link\s+(?P<project>[\w][\w\s.-]{1,80}?)\s+(?P<path>.+?)\s*\.?\s*$"
)


def _clean_project_phrase(raw: str) -> str:
    p = (raw or "").strip().strip("`'\"")
    p = re.sub(r"\s+on\s+vercel\s*$", "", p, flags=re.I)
    return p.strip()


def parse_provider_operation_intent(text: str) -> dict[str, Any] | None:
    """
    Parse NL provider operation intent.

    Returns dict with ``intent``, optional ``project_id`` / ``project_phrase``,
    ``environment``, or scan/link metadata. ``None`` when no match.
    """
    raw = (text or "").strip()
    if not raw or len(raw) > 500:
        return None

    if _SCAN_PROVIDERS.match(raw):
        return {"intent": "provider_scan_providers", "raw_text": raw}

    if _SCAN_PROJECTS.match(raw):
        return {"intent": "provider_scan_projects", "raw_text": raw}

    m_link = _LINK.match(raw)
    if m_link:
        return {
            "intent": "provider_link_project",
            "project_phrase": _clean_project_phrase(m_link.group("project")),
            "repo_path": (m_link.group("path") or "").strip(),
            "raw_text": raw,
        }

    intent_name: str | None = None
    project_phrase: str | None = None

    m_logs = _LOGS.match(raw)
    if m_logs:
        intent_name = "provider_logs"
        project_phrase = _clean_project_phrase(m_logs.group("project") or m_logs.group("project2") or "")
    else:
        for pattern, name in (
            (_RESTART, "provider_restart"),
            (_REDEPLOY, "provider_redeploy"),
            (_DEPLOY_PROJECT, "provider_deploy"),
            (_STATUS, "provider_status"),
            (_IS_LIVE, "provider_status"),
            (_INSPECT, "provider_inspect"),
        ):
            m = pattern.match(raw)
            if m:
                intent_name = name
                project_phrase = _clean_project_phrase(m.group("project"))
                break

    if not intent_name:
        return None

    if intent_name not in _PROVIDER_PROJECT_INTENTS:
        return {"intent": intent_name, "raw_text": raw, "environment": parse_environment_from_text(raw)}

    environment = parse_environment_from_text(raw)
    project_id: str | None = None
    candidates: list[dict[str, Any]] = []

    if project_phrase:
        project_id, candidates = extract_project_slug_from_phrase(project_phrase)
    if not project_id and not candidates:
        project_id, candidates = match_known_project_in_tokens(raw)

    out: dict[str, Any] = {
        "intent": intent_name,
        "raw_text": raw,
        "environment": environment,
        "provider": "vercel",
        "project_phrase": project_phrase,
        "project_id": project_id,
        "candidates": candidates,
    }
    return out


__all__ = ["parse_provider_operation_intent"]
