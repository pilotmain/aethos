# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deterministic extraction of durable preferences from soul.md + memory.md text."""

from __future__ import annotations

import re
from typing import Any


def empty_memory_preferences() -> dict[str, Any]:
    return {
        "preferred_response_format": None,
        "preferred_cursor_format": None,
        "preferred_dev_flow": None,
        "preferred_approval_style": None,
        "preferred_project": None,
        "owner_third_pronoun": None,
    }


def extract_memory_preferences(memory_text: str, soul_text: str = "") -> dict[str, Any]:
    prefs = empty_memory_preferences()
    blob = f"{soul_text}\n{memory_text}".lower()

    # Cursor / IDE instruction shape
    if re.search(
        r"(?i)(one strict plain text block|single plain text block|one plain text block|"
        r"plain text block only|strict plain text|single block of plain text)",
        blob,
    ):
        prefs["preferred_cursor_format"] = "single_plain_text_block"

    if "bullet" in blob and re.search(
        r"(?i)prefer.*bullet|bullets|use bullets", blob
    ):
        prefs["preferred_response_format"] = "bullets"
    elif re.search(r"(?i)concise|short answer|brief reply|terse", blob):
        prefs["preferred_response_format"] = "concise"

    if re.search(
        r"(?i)(ask before|always ask|human approval|approve first|explicit approval)", blob
    ):
        prefs["preferred_approval_style"] = "explicit"
    elif re.search(r"(?i)(minimal approval|fast track|ship quickly)", blob):
        prefs["preferred_approval_style"] = "fast"

    if re.search(
        r"(?i)(autonomous.?cli|aider|run.?cli|terminal.?agent)", blob
    ):
        prefs["preferred_dev_flow"] = "autonomous_cli"
    elif re.search(r"(?i)(ide handoff|cursor handoff|open in ide)", blob):
        prefs["preferred_dev_flow"] = "ide_handoff"

    m = re.search(
        r"(?i)(?:preferred|default)\s+project\s*[:#\s-]+\s*([a-z0-9][a-z0-9_-]*)",
        memory_text + "\n" + soul_text,
    )
    if m:
        prefs["preferred_project"] = m.group(1).strip().lower()
    else:
        m2 = re.search(
            r"(?i)project\s+key\s*[:#\s-]+\s*([a-z0-9][a-z0-9_-]*)",
            memory_text + "\n" + soul_text,
        )
        if m2:
            prefs["preferred_project"] = m2.group(1).strip().lower()

    combined = f"{soul_text}\n{memory_text}"
    cl = combined.lower()
    if re.search(
        r"(?i)raya\s+is\s+male"
        r'|pronouns?:?\s*(?:\*\*)?he/him'
        r'|\bhe/him\b',
        cl,
    ) and re.search(r"(?i)raya|creator|founder|nexa", cl):
        prefs["owner_third_pronoun"] = "he"
    elif re.search(
        r"(?i)pronouns?:?\s*they|they/them|non-?binary",
        cl,
    ) and re.search(r"(?i)raya|creator|owner", cl):
        prefs["owner_third_pronoun"] = "they"
    elif re.search(
        r"(?i)pronouns?:?\s*she|she/her|female(?!,|\s*line)",
        cl,
    ) and re.search(r"(?i)raya|creator|owner", cl):
        prefs["owner_third_pronoun"] = "she"

    return prefs


def get_memory_preferences_dict() -> dict[str, Any]:
    try:
        from app.services.safe_llm_gateway import read_safe_system_memory_snapshot

        snap = read_safe_system_memory_snapshot()
    except Exception:  # noqa: BLE001
        return empty_memory_preferences()
    return extract_memory_preferences(snap.memory, snap.soul)


def count_non_empty_preferences(prefs: dict[str, Any]) -> int:
    return sum(1 for v in prefs.values() if v is not None and str(v).strip())


def user_requests_cursor_instructions(text: str) -> bool:
    t = (text or "").lower()
    keys = (
        "cursor",
        "cursor-ready",
        "for cursor",
        "paste for cursor",
        "instruction for cursor",
        "cursor instruction",
        "tell cursor",
        "ask cursor",
    )
    return any(k in t for k in keys)


def strip_markdown_fences_for_plain_block(s: str) -> str:
    text = (s or "").strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def maybe_apply_single_plain_cursor_block(message: str, user_message: str) -> str:
    prefs = get_memory_preferences_dict()
    if prefs.get("preferred_cursor_format") != "single_plain_text_block":
        return message
    if not user_requests_cursor_instructions(user_message):
        return message
    return strip_markdown_fences_for_plain_block(message)


def preference_formatting_system_instructions() -> str:
    prefs = get_memory_preferences_dict()
    lines: list[str] = []
    if prefs.get("preferred_cursor_format") == "single_plain_text_block":
        lines.append(
            "When the user asks for Cursor (or IDE) instructions, respond with exactly one plain-text block: "
            "no markdown code fences, no bold headings—only the raw instructions they can paste."
        )
    if prefs.get("preferred_response_format") == "concise":
        lines.append("Prefer concise replies unless the user asks for depth.")
    if prefs.get("preferred_response_format") == "bullets":
        lines.append("When listing steps or options, prefer short bullets.")
    if prefs.get("preferred_approval_style") == "explicit":
        lines.append("Call out when human approval is needed before risky or irreversible actions.")
    return "\n".join(lines)


def general_answer_memory_formatting_block() -> str:
    s = preference_formatting_system_instructions()
    s2 = identity_pronoun_system_instructions()
    parts = [x for x in (s, s2) if (x or "").strip()]
    return f"\n\n" + "\n\n".join(parts) if parts else ""


def get_effective_owner_pronoun(
    user_preferences: dict[str, str] | None = None,
) -> str | None:
    """
    When referring to a named owner/creator, prefer this third-person set.
    DB keys override soul.md; values are he / she / they.
    """
    up = user_preferences or {}
    for k in (
        "learned:owner_pronoun",
        "learned:owner_pronouns",
        "owner_pronoun",
    ):
        raw = (up.get(k) or "").strip().lower()
        if not raw:
            continue
        if re.match(
            r"^(he|he/|him|his|m|male|masc(uline)?)(\b|/)",
            raw,
        ) or raw.startswith("he/"):
            return "he"
        if re.match(r"^(she|she/|her|f|female|fem)(\b|/)", raw) or raw.startswith("she/"):
            return "she"
        if re.match(r"^(they|non|enby|nb|them)(\b|/)", raw) or "they" == raw:
            return "they"
    prefs = get_memory_preferences_dict()
    o = prefs.get("owner_third_pronoun")
    if o in ("he", "she", "they"):
        return o
    return None


def identity_pronoun_system_instructions() -> str:
    p = get_effective_owner_pronoun(None) or "unknown"
    base = [
        "Identity and pronouns:",
        "- Do not infer or assume gender, pronouns, or name from names alone (e.g. a name is not a pronoun).",
        "- If soul.md or <user_preferences> state how to refer to the user or a named creator, use that in third person.",
        "- If pronouns are not stated, use neutral phrasing, the person’s name, or they/them; do not default to she for names that are ambiguous to you.",
    ]
    if p == "he":
        base.append(
            "Nexa’s creator profile in soul.md: he/him. Use he/him for that person when the question is about Raya, not a gender guess from the name."
        )
    if p == "they":
        base.append("Owner profile: they/them. Use that in third person when the profile is about the same person.")
    if p == "she":
        base.append("Owner profile: she/her. Use that in third person when the profile is about the same person.")
    return " ".join(base)
