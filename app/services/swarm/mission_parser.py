"""
Strict mission document parser — only explicit per-agent task lines (no LLM).

Extracts title from @boss run mission "…" or Mission: "…", tasks from "@handle: …" lines,
and dependency edges from @mentions inside each task line.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.custom_agents import normalize_agent_key

# Lines like: @researcher-pro: find breakthroughs.
_RE_AGENT_TASK_LINE = re.compile(r"(?im)^\s*@([\w-]{2,64})\s*:\s*(.+)$")

_RE_BOSS_RUN_MISSION = re.compile(r'(?is)@boss\s+run\s+mission\s+"([^"]+)"')

_RE_TITLE_QUOTED = re.compile(
    r'(?is)(?:execute\s+)?(?:System\s+)?Mission\s*:\s*"([^"]+)"|Mission\s*:\s*"([^"]+)"'
)

_RE_SINGLE_CYCLE = re.compile(r"(?i)\bsingle[- ]?cycle\b")

# Skip prose blocks unless they contain explicit @handle: lines (handled by global regex).
_IGNORE_SECTION_HEADERS = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(Behavior rules|Execution rules|Visual formatting|"
    r"Watchlist behavior|Dashboard behavior|Goal|Expected output)\s*:?\s*$"
)


def _norm_dep_tokens(task_text: str, *, self_handle: str) -> list[str]:
    """Other @handles referenced inside a task line become dependency keys."""
    self_k = normalize_agent_key(self_handle)
    seen: list[str] = []
    for m in re.finditer(r"@([\w-]{2,64})\b", task_text or ""):
        k = normalize_agent_key(m.group(1))
        if not k or k == self_k or k == "boss":
            continue
        if k not in seen:
            seen.append(k)
    return seen


def parse_mission(text: str) -> dict[str, Any] | None:
    """
    Return a structured mission dict or None when the text is not a strict mission document.

    Requires:
    - A quoted mission title from @boss run mission "…" or Mission: "…" / System Mission: "…"
    - At least one non-boss per-agent line ``@handle: task`` with task length ≥ 5
    """
    raw = (text or "").strip()
    if len(raw) < 24:
        return None

    title: str | None = None
    m_br = _RE_BOSS_RUN_MISSION.search(raw)
    if m_br:
        title = (m_br.group(1) or "").strip()
    if not title:
        mq = _RE_TITLE_QUOTED.search(raw)
        if mq:
            title = (mq.group(1) or mq.group(2) or "").strip()

    tasks_raw: list[dict[str, Any]] = []
    for m in _RE_AGENT_TASK_LINE.finditer(raw):
        hk = normalize_agent_key(m.group(1))
        task_body = (m.group(2) or "").strip()
        if hk == "boss":
            continue
        if len(task_body) < 5:
            continue
        deps = _norm_dep_tokens(task_body, self_handle=hk)
        tasks_raw.append(
            {
                "agent_handle": hk,
                "task": task_body[:2000],
                "depends_on": deps,
            }
        )

    if not tasks_raw:
        return None
    if not title or len(title) < 2:
        return None

    single_cycle = bool(_RE_SINGLE_CYCLE.search(raw))

    return {
        "title": title[:2000],
        "single_cycle": single_cycle,
        "tasks": tasks_raw,
    }
