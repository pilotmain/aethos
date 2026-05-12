# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Detect user intent to create one or more custom agents from natural language.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Triggers: “create an agent”, “create 3 agents”, “build me a personal agent”, etc.
# Deliberately excludes vague phrases like “create multi agents” (capability question).
_RE_CREATE = re.compile(
    r"(?is)\b("
    r"create\s+an?\s+agent\b|"
    r"create\s+\d+\s+agents?\b|"
    r"add\s+an?\s+agent\b|"
    r"make(?:\s+me)?\s+agent\b|"
    r"build\s+me.+(personal\s+)?(custom\s+)?agent\b|"
    r"I\s+want.+(custom|personal).+agents?\b|"
    r"add\s+an?\s+agent\s+called"
    r")",
)


@dataclass
class CreationParse:
    kind: str  # "list" | "single" | "none"
    title_lines: list[str]


_REGULATED_MISUSE = re.compile(
    r"(?is)\b("
    r"final\s+legal\s+advice|give\s+(me\s+)?final\s+legal"
    r"|act\s+as\s+(my\s+)?(licensed\s+)?attorney"
    r"|replace\s+(your\s+|my\s+)?lawyer"
    r"|provide\s+(final\s+)?(medical|tax)\s+advice"
    r")\b",
)


def is_regulated_professional_misuse_request(text: str) -> bool:
    """User asks the agent to stand in for a licensed professional — refuse that framing."""
    return bool(_REGULATED_MISUSE.search(text or ""))


def is_custom_agent_capability_inquiry(text: str) -> bool:
    """
    User asks whether they can define / use custom agents without explicit create-my-agent syntax.
    Must not overlap ``is_custom_agent_creation_intent`` (handled first in pipeline).
    """
    if is_custom_agent_creation_intent(text):
        return False
    raw = (text or "").strip()
    if not raw:
        return False
    tl = raw.lower()

    # Broad capability questions about custom agents
    if ("custom agent" in tl or "personal agent" in tl or "my own agent" in tl or "own agent" in tl) and (
        "?" in raw or tl.startswith(("can ", "could ", "do you ", "does nexa", "is it possible"))
    ):
        return True
    if any(
        x in tl
        for x in (
            "can i have my own agent",
            "can i get my own agent",
            "can i create my own agent",
            "define my own agent",
            "build my own agent",
            "role-specific agent",
            "senior attorney",
            "acts as a lawyer",
            "agent who acts as",
            "agent that acts as",
        )
    ):
        return True
    if ("can i" in tl or "could i" in tl) and "agent" in tl and any(
        x in tl for x in ("attorney", "lawyer", "legal", "counsel", "cpa", "doctor")
    ):
        return True
    return False


def is_custom_agent_creation_intent(text: str) -> bool:
    t = (text or "").strip()
    if not t or t.startswith("/"):
        return False
    m = _RE_CREATE.search(t)
    if m:
        return True
    tl = t.lower()
    for needle in (
        "build me a personal agent",
        "add an agent called",
        "create me an agent",
        "create an agent",
        "custom agent",
        "personal agent",
        "add an agent",
        "make an agent for",
    ):
        if needle in tl:
            return True
    if re.search(r"(?is)^\s*create\s+me.{0,200}agent", t):
        return True
    return False


def _strip_bullet(line: str) -> str:
    s = re.sub(
        r"^[\s•\-\*]*(\d{1,2}|[a-zA-Z0-9]{1,2})[\).]\s*",
        "",
        (line or "").strip(),
    )
    return s.strip()


def parse_agent_title_lines_from_message(text: str) -> list[str]:
    """
    After a 'create N agents' intro, list items on separate lines, or
    a single 'called X' pattern.
    """
    raw = (text or "").strip()
    if not raw:
        return []
    numbered: list[str] = []
    for line in raw.splitlines():
        m = re.match(r"^\s*(\d+)[\).]\s*(.+)$", line)
        if m and m.group(2).strip():
            numbered.append(m.group(2).strip()[:400])
    if len(numbered) >= 1:
        return [x for x in numbered if x][:24]
    out: list[str] = []
    m_called = re.search(
        r"(?is)(add\s+an?\s+agent|create\s+an?\s+agent|make\s+an?\s+agent)\s+called\s+['\"`]?(.+?)['\"`]?\s*$",
        raw,
    )
    if m_called:
        one = m_called.group(2).strip()
        return [one] if one else []

    for line in raw.splitlines():
        t = _strip_bullet(line)
        if not t or len(t) > 400:
            continue
        tl = t.lower()
        if re.match(
            r"^(create|make|build|add|I want).{0,40}agent", tl
        ) and "called" not in tl:
            continue
        if tl in ("", "and", "or", "ok", "yes", "thanks"):
            continue
        if any(
            x in tl
            for x in (
                "try:",
                "nexus",
            )
        ):
            continue
        if re.match(
            r"^[\s\-•]*$",
            line,
        ):  # noqa: W505
            continue
        if len(out) < 1 and re.match(
            r"(?i)^(create|make|build|add|here).{0,80}agents?$",
            t,
        ) and not re.search(
            r"[\)\]]",
            t,
        ):  # skip header only line
            if ":" in t and len(t) < 120:
                # "Create me five agents:"  ->  skip
                continue
        if len(out) >= 24:  # hard cap
            break
        out.append(t)
    if len(out) == 0:
        m = re.search(
            r"(?i)agents?[\s:=\-]+\s*(.+)$",
            raw,
            re.DOTALL,
        )
        if m and m.group(1):
            chunk = m.group(1)
            for part in re.split(
                r",|\band\b|;",
                chunk,
            ):
                p2 = (part or "").strip().strip("•-*").strip("1234567890.)").strip()
                if p2 and len(p2) < 400:
                    out.append(p2)
    if len(out) == 0:
        m2 = re.search(
            r"(?i)called\s+['\"`]?(.+?)['\"`]?(\.|\!|$)", raw, re.DOTALL
        )
        if m2 and m2.group(1) and m2.group(1).count("\n") < 1:
            out = [m2.group(1).strip()]
    return [x for x in out if x and len(x) < 500]
