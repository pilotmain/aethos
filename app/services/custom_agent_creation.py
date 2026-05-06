"""
Structured custom-agent creation (product primitive).

Parse → validate → persist → confirmation. Does not use host_executor, dev jobs, or tool routing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.custom_agents import (
    can_user_create_custom_agents,
    create_custom_agent,
    normalize_agent_key,
    validate_dangerous_capability_request,
)


def is_create_custom_agent_intent(text: str) -> bool:
    """Aligned with intent_classifier: stripped message starts with 'create' and contains 'agent'."""
    t = (text or "").strip()
    tl = t.lower()
    return bool(tl.startswith("create") and "agent" in tl)


@dataclass
class CreationSpec:
    display_title: str
    capabilities: list[str]
    guardrails: list[str]


def _bullet_line(line: str) -> str | None:
    s = (line or "").strip()
    if not s:
        return None
    if re.match(r"^[\s\-•\*]+$", s):
        return None
    s = re.sub(r"^[\s\-•\*]+\s*", "", s)
    return s.strip() or None


def _extract_sections(lines: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Returns (header_lines, capability_lines, guardrail_lines)."""
    header: list[str] = []
    caps: list[str] = []
    guards: list[str] = []
    mode = "header"
    for line in lines:
        ls = line.strip()
        if re.match(r"(?i)^capabilities\s*:?\s*$", ls):
            mode = "cap"
            continue
        if re.match(r"(?i)^guardrails\s*:?\s*$", ls):
            mode = "guard"
            continue
        if mode == "header":
            header.append(line)
        elif mode == "cap":
            b = _bullet_line(line)
            if b:
                caps.append(b)
        elif mode == "guard":
            b = _bullet_line(line)
            if b:
                guards.append(b)
    return header, caps, guards


def _extract_title_from_header(header: str) -> str | None:
    h = header.strip()
    if not h:
        return None
    first = h.split("\n", 1)[0].strip()

    m = re.search(r"@([\w][\w-]{0,62})\b", first)
    if m:
        return m.group(1).strip()

    m = re.search(r"(?is)(?:agent\s+called|named)\s+['\"]?([^'\"\n]+)", h)
    if m:
        return m.group(1).strip()

    m = re.search(r"(?i)\bagent\s+(.+)$", first)
    if m:
        tail = m.group(1).strip()
        tail = re.sub(r"\s+agent\s*$", "", tail, flags=re.I).strip()
        if tail:
            return tail

    m = re.search(r"(?i)^(?:create\s+(?:a\s+|an\s+)?)(.+?)\s+agent\s*$", first)
    if m:
        inner = m.group(1).strip()
        if inner:
            return inner

    return None


def parse_creation_spec(text: str) -> CreationSpec | None:
    """
    Best-effort parse for messages starting with create…agent.
    Expects optional Capabilities / Guardrails sections (Markdown-style bullets ok).
    """
    raw = (text or "").strip()
    if not is_create_custom_agent_intent(raw):
        return None

    lines = raw.splitlines()
    header_lines, caps, guards = _extract_sections(lines)
    header = "\n".join(header_lines).strip()
    title = _extract_title_from_header(header)
    if not title:
        return None

    return CreationSpec(
        display_title=title[:400],
        capabilities=caps[:40],
        guardrails=guards[:40],
    )


def _build_system_prompt(spec: CreationSpec) -> str:
    parts = [
        "You are an AethOS custom specialist agent. Reply helpfully within your described scope. "
        "You do not have autonomous dev, deployment, or host execution unless separately enabled.",
        "",
        f"Role: {spec.display_title}",
    ]
    if spec.capabilities:
        parts.append("")
        parts.append("Capabilities:")
        parts.extend(f"- {c}" for c in spec.capabilities)
    if spec.guardrails:
        parts.append("")
        parts.append("Guardrails:")
        parts.extend(f"- {g}" for g in spec.guardrails)
    return "\n".join(parts).strip()


def _build_description(spec: CreationSpec) -> str:
    bits = [spec.display_title]
    if spec.capabilities:
        bits.append("Capabilities: " + "; ".join(spec.capabilities[:6]))
    return " — ".join(bits)[:2000]


def format_creation_confirmation(
    *,
    agent_key: str,
    capabilities: list[str],
    guardrails: list[str],
) -> str:
    lines = [
        f"Agent created: @{agent_key}",
        "",
        "Capabilities:",
    ]
    if capabilities:
        lines.extend(f"- {c}" for c in capabilities)
    else:
        lines.append("- (Ask this agent for concrete tasks — you can refine scope any time.)")

    lines.extend(["", "Guardrails:"])
    if guardrails:
        lines.extend(f"- {g}" for g in guardrails)
    else:
        lines.append("- AethOS LLM-only profile — no automatic host or dev actions.")

    lines.extend(
        [
            "",
            "You can now use it by mentioning:",
            f"@{agent_key} review this contract",
        ]
    )
    return "\n".join(lines)


def run_create_custom_agent_flow(db: Session, app_user_id: str, user_text: str) -> str:
    """Execute creation flow; assumes caller matched create_custom_agent intent."""
    if not is_create_custom_agent_intent(user_text):
        return (
            "Say **create agent …** with a short name (optionally add Capabilities / Guardrails sections)."
        )

    ok, err = can_user_create_custom_agents(db, app_user_id)
    if not ok:
        return (err or "Custom agents aren’t available on this account right now.").strip()

    danger = validate_dangerous_capability_request(user_text)
    spec = parse_creation_spec(user_text)
    if spec is None:
        return (
            "I need an agent **name** or `@handle` on the first line, for example:\n"
            "**create agent legal-reviewer**\n\n"
            "Optional blocks:\n"
            "**Capabilities:** …\n"
            "**Guardrails:** …"
        )

    force_key = normalize_agent_key(spec.display_title)
    if not force_key:
        return "Pick a clearer agent name (letters, numbers, hyphen or underscore)."

    agent = create_custom_agent(
        db,
        app_user_id,
        spec.display_title,
        description=_build_description(spec),
        system_prompt=_build_system_prompt(spec),
        force_agent_key=force_key,
    )
    body = format_creation_confirmation(
        agent_key=agent.agent_key,
        capabilities=spec.capabilities,
        guardrails=spec.guardrails,
    )
    if danger:
        body = f"{body}\n\n{danger}"
    return body


def try_create_custom_agent_primitive(db: Session, app_user_id: str, user_text: str) -> str | None:
    """
    If this matches the strict create+agent intent and we can parse a title, run creation and return text.
    Otherwise return None so broader conversational creation can run.
    """
    if not is_create_custom_agent_intent(user_text):
        return None
    if parse_creation_spec(user_text) is None:
        return None
    return run_create_custom_agent_flow(db, app_user_id, user_text)
