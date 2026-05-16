# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Project name extraction for natural-language provider operations (Phase 2 Step 5)."""

from __future__ import annotations

import re
from typing import Any

from app.projects.project_registry_service import resolve_project_slug
from app.projects.vercel_link import slugify_project_id
from app.runtime.runtime_state import ensure_operator_context_schema, load_runtime_state


def _registry_rows() -> dict[str, dict[str, Any]]:
    st = load_runtime_state()
    ensure_operator_context_schema(st)
    projects = (st.get("project_registry") or {}).get("projects") or {}
    return projects if isinstance(projects, dict) else {}


def _normalize_token(raw: str) -> str:
    return slugify_project_id((raw or "").strip())


def extract_project_slug_from_phrase(project_phrase: str) -> tuple[str | None, list[dict[str, Any]]]:
    """
    Resolve a free-text project phrase using registry aliases first.

    Returns ``(project_id, candidates)`` — ``project_id`` is set only when unique.
    """
    phrase = (project_phrase or "").strip()
    if not phrase:
        return None, []
    # Exact slug / alias match via registry service.
    pid, cands = resolve_project_slug(phrase)
    if pid:
        return pid, cands
    # Slugify phrase and retry (Invoice Pilot → invoice-pilot).
    slug = _normalize_token(phrase)
    if slug and slug != phrase.lower():
        pid2, cands2 = resolve_project_slug(slug)
        if pid2:
            return pid2, cands2
        if cands2:
            return None, cands2
    return None, cands


def parse_environment_from_text(text: str) -> str:
    low = (text or "").lower()
    if re.search(r"\bpreview\b", low):
        return "preview"
    if re.search(r"\b(staging|stage)\b", low):
        return "preview"
    return "production"


def match_known_project_in_tokens(text: str) -> tuple[str | None, list[dict[str, Any]]]:
    """Fallback: find a registry alias appearing as a token in the message."""
    rows = _registry_rows()
    if not rows:
        return None, []
    low = (text or "").lower()
    hits: list[dict[str, Any]] = []
    for _pid, row in rows.items():
        if not isinstance(row, dict):
            continue
        aliases = {str(a).lower() for a in (row.get("aliases") or []) if a}
        aliases.add(str(row.get("project_id") or "").lower())
        aliases.add(str(row.get("name") or "").lower())
        for alias in aliases:
            if not alias or len(alias) < 2:
                continue
            if re.search(rf"\b{re.escape(alias)}\b", low):
                hits.append(row)
                break
    if len(hits) == 1:
        return str(hits[0].get("project_id") or ""), hits
    return None, hits[:12]
