# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Detect raw product ideas and draft Nexa project profiles (not tied to one repo)."""

from __future__ import annotations

import re
import secrets
from typing import Any

IDEA_PATTERNS: list[str] = [
    "i want to build",
    "i have an idea",
    "i want to create",
    "i want to launch",
    "i'm thinking of building",
    "i am thinking of building",
    "can we build",
    "new project",
]


def looks_like_new_idea(text: str) -> bool:
    t = (text or "").lower()
    if not t.strip() or t.strip().startswith("/"):
        return False
    if len(t) > 2000:
        return False
    return any(p in t for p in IDEA_PATTERNS)


def slugify_project_key(name: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    if not clean:
        clean = "project-" + secrets.token_hex(3)
    return clean[:40]


def extract_idea_summary(text: str) -> dict[str, str]:
    raw = (text or "").strip()
    t = raw.lower()
    s = t
    for phrase in IDEA_PATTERNS:
        s = s.replace(phrase, " ")
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        s = t[:500]
    project_name = s[:60].strip().title() or "New Project"
    if len(project_name) < 2:
        project_name = "New Project"
    project_key = slugify_project_key(s[:80])
    return {
        "summary": raw,
        "project_name": project_name,
        "project_key": project_key,
    }


def recommended_workflow_ids() -> list[str]:
    return ["strategy", "marketing", "dev", "qa", "ops"]


def build_pending_project_payload(idea: dict) -> dict[str, Any]:
    return {
        "project_name": idea["project_name"],
        "project_key": idea["project_key"],
        "summary": idea["summary"],
        "recommended_workflow": recommended_workflow_ids(),
    }


def format_idea_draft_reply(payload: dict) -> str:
    name = (payload.get("project_name") or "Project")[:200]
    key = (payload.get("project_key") or "project")[:80]
    return (
        "Got it — this sounds like a **new project**.\n\n"
        f"**Project draft**\n"
        f"Name: {name}\n"
        f"Key: `{key}`\n\n"
        "**Recommended workflow**:\n"
        "1. Product direction — validate the problem and target user\n"
        "2. Marketing — define positioning and audience\n"
        "3. Development — outline MVP scope\n"
        "4. Quality — define acceptance checks\n"
        "5. Operations — choose deployment path\n\n"
        "Want me to create this as a Nexa project?\n"
        "Reply: **create project**"
    )


def is_create_project_confirmation(text: str) -> bool:
    t = re.sub(r"\s+", " ", (text or "").strip().lower())
    return t in ("create project", "create project.")


RE_CREATE_REPO = re.compile(
    r"(?i)^create\s+repo(?:itory)?\s+for\s+([a-z0-9][a-z0-9_\-]*)\s*\.?\s*$"
)


def match_create_repo_request(text: str) -> str | None:
    m = RE_CREATE_REPO.match((text or "").strip())
    return m.group(1).lower() if m else None
