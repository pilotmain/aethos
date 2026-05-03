"""Heuristic selection of workspace files for the current user turn."""

from __future__ import annotations

import re
from pathlib import Path

from app.services.workspace_intelligence.loader import iter_workspace_files
from app.services.workspace_intelligence.skills_graph import find_skill_chain


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in re.finditer(r"[a-z][a-z0-9]{2,}", (text or "").lower())}


def _score_path(rel: str, text_lower: str, tokens_user: set[str]) -> float:
    base = rel.lower().replace("/", " ")
    score = 0.0
    for t in tokens_user:
        if len(t) < 4:
            continue
        if t in base:
            score += 2.0
        if t in text_lower:
            score += 0.5
    # routing hints
    if "linkedin" in text_lower and "business" in rel:
        score += 1.5
    if "linkedin" in text_lower and "outputs" in rel:
        score += 3.0
    if "transcript" in text_lower or "podcast" in text_lower:
        if "skills" in rel or "processes" in rel:
            score += 2.0
    if "nexa" in text_lower and "projects/nexa" in rel.replace("\\", "/"):
        score += 2.5
    if "client" in text_lower and rel.startswith("clients/"):
        score += 3.0
    return score


def select_workspace_context(
    root: Path,
    user_text: str,
    *,
    project_slug: str | None = None,
    max_candidates: int = 24,
) -> tuple[list[str], list[str]]:
    """
    Return (ordered_relative_paths, skill_ids) for :func:`build_pack`.

    Never loads full corpus — scores discovered paths only.
    """
    text = (user_text or "").strip()
    text_lower = text.lower()
    tt = _tokens(text)

    available = iter_workspace_files(root)
    scored: list[tuple[float, str]] = []
    for rel in available:
        s = _score_path(rel, text_lower, tt)
        if project_slug and rel.startswith(f"projects/{project_slug}.md"):
            s += 6.0
        if rel in ("user.md", "personality.md"):
            s += 0.8
        if s > 0 or rel in ("personality.md", "user.md"):
            scored.append((s, rel))

    scored.sort(key=lambda x: (-x[0], x[1]))
    picked = [rel for _, rel in scored[:max_candidates]]

    # Ensure core tone files early when something matched.
    core = [x for x in ("personality.md", "user.md") if x in available]
    ordered: list[str] = []
    for c in core:
        if c in picked and c not in ordered:
            ordered.append(c)
    for rel in picked:
        if rel not in ordered:
            ordered.append(rel)

    skills = find_skill_chain(text)
    return ordered, skills


__all__ = ["select_workspace_context"]
