# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""User-facing response cleanup helpers used by the OSS app."""

from __future__ import annotations

import re
from typing import Any

LIST_FORMATTING_LLM_GUIDANCE = (
    "Use clean Markdown lists. Prefer `1. item` and `- item`; do not bold list markers."
)

_BOLD_NUMBER_MARKER = re.compile(r"(?m)^(\s*)\*\*(\d+)\.\*\*\s*")
_JUNK_BULLET = re.compile(r"(?m)^(\s*)[*#]+\s*-\s*")
_JUNK_NUMBER = re.compile(r"(?m)^(\s*)[*#\-\s]*([0-9]+)\.\*?\s*#?\s*")
_ROBOTIC_OPENERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?is)^As an AI(?: language model| assistant)?,?\s*"), ""),
    (re.compile(r"(?is)^I(?:'m| am) an AI[^.\n]{0,120}\.\s*"), ""),
    (re.compile(r"(?is)^Based on (?:the )?(?:information|context|details)[^.]{0,160}\.\s*"), ""),
    (re.compile(r"(?is)^(?:In summary|To summarize|Overall),?\s*"), ""),
)
_FILLER_PARA = re.compile(
    r"(?is)^(I hope this helps\.?|Feel free to ask.*|Let me know if you (have )?any questions\.?)\s*$"
)


def _transform_outside_fences(text: str, transform) -> str:
    out: list[str] = []
    block: list[str] = []
    in_fence = False
    for line in str(text).splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            if block:
                out.append(transform("".join(block)))
                block.clear()
            out.append(line)
            in_fence = not in_fence
            continue
        if in_fence:
            out.append(line)
        else:
            block.append(line)
    if block:
        out.append(transform("".join(block)))
    return "".join(out)


def _clean_plain_block(block: str) -> str:
    block = _BOLD_NUMBER_MARKER.sub(r"\1\2. ", block)
    block = _JUNK_BULLET.sub(r"\1- ", block)
    block = _JUNK_NUMBER.sub(r"\1\2. ", block)
    block = re.sub(r"[ \t]+\n", "\n", block)
    block = re.sub(r"\n{3,}", "\n\n", block)
    return block


def clean_response_formatting(text: str) -> str:
    """Normalize common malformed Markdown while preserving fenced code."""
    if not isinstance(text, str) or not text:
        return text
    return _transform_outside_fences(text, _clean_plain_block).strip()


def _humanize_response(text: str) -> str:
    if not text or not str(text).strip():
        return text
    out = str(text)
    for rx, repl in _ROBOTIC_OPENERS:
        out = rx.sub(repl, out, count=1)
    return re.sub(r"\n{4,}", "\n\n", out).strip()


def _minimize_response_length(text: str, *, max_chars: int = 14_000) -> str:
    if not text or len(text) <= max_chars:
        return text
    window = text[:max_chars]
    cut = window.rfind("\n\n")
    if cut > max_chars // 3:
        return text[:cut].rstrip() + "\n\n..."
    return text[: max_chars - 3].rstrip() + "..."


def _drop_filler_and_duplicates(text: str) -> str:
    if not text or not text.strip():
        return text
    out: list[str] = []
    seen: set[str] = set()
    for block in re.split(r"\n\s*\n+", text):
        raw = block.strip()
        if not raw or _FILLER_PARA.match(raw):
            continue
        norm = re.sub(r"\s+", " ", raw.lower()).rstrip(".!? ")
        if len(norm) >= 8 and norm in seen:
            continue
        seen.add(norm)
        out.append(raw)
    return "\n\n".join(out).strip()


def _owner_forms(pronoun: str) -> tuple[str, str, str]:
    p = (pronoun or "").strip().lower()
    if p == "he":
        return "he", "him", "his"
    if p == "she":
        return "she", "her", "her"
    return "they", "them", "their"


def _apply_owner_pronoun_fixes_prose(text: str, owner_pronoun: str | None = None) -> str:
    """Fix obvious Raya pronoun slips only on local Raya-focused prose lines."""
    if not text or not owner_pronoun:
        return text
    subj, obj, poss = _owner_forms(owner_pronoun)
    if subj == "she":
        return text

    def fix_line(line: str) -> str:
        if "raya" not in line.lower():
            return line
        line = re.sub(r"\b[Ss]he\b", subj.capitalize(), line)
        line = re.sub(r"\b[Hh]er\b", poss.capitalize(), line)
        line = re.sub(r"\b hers\b", f" {poss}", line)
        return re.sub(r"\bHers\b", poss.capitalize(), line)

    return "\n".join(fix_line(line) for line in str(text).split("\n"))


def soften_capability_downgrade_phrases(text: str) -> str:
    """Avoid falsely implying the whole system is read-only."""
    if not text:
        return text
    out = re.sub(
        r"(?i)\bI am read-only\b",
        "I can use read-only web tools here",
        str(text),
    )
    out = re.sub(
        r"(?i)\bI'm read-only\b",
        "I can use read-only web tools here",
        out,
    )
    return out


def _owner_pronoun_from_preferences(user_preferences: dict[str, Any] | None) -> str | None:
    if not user_preferences:
        return None
    for key in ("learned:owner_pronoun", "owner_pronoun", "owner_third_pronoun"):
        val = str(user_preferences.get(key) or "").strip().lower()
        if val in {"he", "she", "they"}:
            return val
    return None


def finalize_user_facing_text(
    text: str,
    *,
    user_preferences: dict[str, Any] | None = None,
    max_chars: int = 14_000,
) -> str:
    """Run the final UX cleanup pipeline used by chat and web replies."""
    out = clean_response_formatting(text)
    out = soften_capability_downgrade_phrases(out)
    out = _humanize_response(out)
    out = _drop_filler_and_duplicates(out)
    out = _apply_owner_pronoun_fixes_prose(out, _owner_pronoun_from_preferences(user_preferences))
    return _minimize_response_length(out, max_chars=max_chars)


__all__ = [
    "LIST_FORMATTING_LLM_GUIDANCE",
    "clean_response_formatting",
    "finalize_user_facing_text",
    "soften_capability_downgrade_phrases",
    "_apply_owner_pronoun_fixes_prose",
]
