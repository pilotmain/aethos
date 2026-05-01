"""
User-facing response cleanup: normalizes messy LLM list/bullet patterns without
stripping meaningful markdown (## headings, links, code fences, intentional emphasis).

User-visible replies should go through :func:`finalize_user_facing_text` (or at minimum
:func:`clean_response_formatting`) from ``legacy_behavior_utils.build_response``,
``agent_orchestrator`` sinks, and ``web_chat_service._finalize_web_result``.
:func:`finalize_user_facing_text` applies list cleanup plus a light owner-pronoun check when
memory + preferences say to.
"""
from __future__ import annotations

import re

# Injected into response composer system prompts; reduces junk before post-processing
LIST_FORMATTING_LLM_GUIDANCE = (
    'Use clean numbered lists like "1. Item" and bullets like "- Item". Do not use '
    "markdown artifacts like **1.**, *#, or stacked symbols in list markers."
)

# **1.** or **1.** then spaces → 1. (one space) — consume trailing space to avoid 1.  First
_RE_BOLD_ORD = re.compile(r"\*\*(\d+)\.\*\*\s*")

# Line starts: "1.*#- rest" or "1. * rest" (junk after the dot)
_RE_NUM_LEAD_JUNK = re.compile(r"^(\s*)(\d+)\.(\s*[\*#•\-]|\*+)+\s*")

# Line starts: multiple symbols before text (e.g. *#- Item), not ##, not ---
_RE_SYMBOL_STACK = re.compile(r"^(\s*)[\*#•\-]{2,}\s+")

# Line starts: single * or • for list → "- "
_RE_STAR_BULLET = re.compile(r"^(\s*)\*\s+")
_RE_BULLET_CHAR = re.compile(r"^(\s*)[•·]\s+")

# "- * Item" or " - * " style → single bullet
_RE_DASH_THEN_STAR = re.compile(r"^(\s*)-\s+\*\s+")

# Markdown "**- point" (bold hyphen list junk) at line start
_RE_BOLD_DASH = re.compile(r"^(\s*)\*\*-\s+")


def _normalize_section_spacing_prose(text: str) -> str:
    """
    In prose: collapse 3+ blank lines, ensure a blank line before ## headings, one after heading line
    when body follows. Does not run inside code fences.
    """
    if not (text and text.strip()):
        return text
    t = re.sub(r"\n{3,}", "\n\n", text)
    t = re.sub(r"([^\n])\n(##\s+)", r"\1\n\n\2", t)
    t = re.sub(
        r"(?m)(^##[^\n]+)\n(?=[^\n#\s])",
        r"\1\n\n",
        t,
    )
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t


def _clean_prose_segment(seg: str) -> str:
    if not seg:
        return seg
    t = _RE_BOLD_ORD.sub(r"\1. ", seg)
    lines: list[str] = []
    for line in t.splitlines(keepends=True):
        if line.endswith("\n"):
            core, nl = line[:-1], "\n"
        else:
            core, nl = line, ""
        lines.append(_clean_list_line(core) + nl)
    return _normalize_section_spacing_prose("".join(lines))


def _clean_list_line(line: str) -> str:
    s = line
    st = s.lstrip()
    if st.startswith("##"):
        return s
    if re.match(r"^---\s*$", st):
        return s
    if re.match(r"^---\S", st):
        return s
    m = _RE_NUM_LEAD_JUNK.match(s)
    if m:
        rest = s[m.end() :]
        s = f"{m.group(1)}{m.group(2)}. {rest.lstrip()}"
    m2 = _RE_SYMBOL_STACK.match(s)
    if m2:
        rest2 = s[m2.end() :]
        s = f"{m2.group(1)}- {rest2.lstrip()}"
    mbd = _RE_BOLD_DASH.match(s)
    if mbd:
        s = f"{mbd.group(1)}- {s[mbd.end() :].lstrip()}"
    mds = _RE_DASH_THEN_STAR.match(s)
    if mds:
        s = f"{mds.group(1)}- {s[mds.end() :].lstrip()}"
    m3 = _RE_STAR_BULLET.match(s)
    if m3:
        rest3 = s[m3.end() :]
        s = f"{m3.group(1)}- {rest3}"
    m4 = _RE_BULLET_CHAR.match(s)
    if m4:
        s = f"{m4.group(1)}- {s[m4.end():]}"
    return s


def _split_preserve_fences(text: str) -> list[tuple[str, bool]]:
    """(chunk, is_fence) in order."""
    out: list[tuple[str, bool]] = []
    i = 0
    n = len(text)
    while i < n:
        j = text.find("```", i)
        if j == -1:
            out.append((text[i:], False))
            break
        if j > i:
            out.append((text[i:j], False))
        k = text.find("```", j + 3)
        if k == -1:
            out.append((text[j:], True))
            break
        out.append((text[j : k + 3], True))
        i = k + 3
    if not out:
        out = [(text, False)]
    return out


def _apply_owner_pronoun_fixes_prose(text: str, owner_third: str | None) -> str:
    """
    When memory + prefs say the Nexa owner/creator (Raya) is he/him, fix an obvious
    she/her slip only on lines that also mention Raya. Skips code blocks (caller
    has already run through prose segments when used after clean).
    """
    if not text or (owner_third or "").lower() != "he":
        return text
    if "raya" not in text.lower():
        return text
    if not re.search(r"(?i)\b(she|her|herself)\b", text):
        return text

    def _one_line(s: str) -> str:
        if not re.search(r"(?i)\braya\b", s) or not re.search(
            r"(?i)\b(she|her|herself)\b", s
        ):
            return s
        t = s
        t = re.sub(r"(?i)\bShe\b", "He", t)
        t = re.sub(r"(?i)\bshe\b", "he", t)
        t = re.sub(r"(?i)\bherself\b", "himself", t)
        t = re.sub(
            r"(?i)(to|for|with|from|about|at|in|on|of|over|by|toward|towards)\s+her\b",
            r"\1 him",
            t,
        )
        t = re.sub(
            r"(?i) her (idea|work|name|book|path|goals?|stance|view|version|build|code|app|vision|team|site|role|focus)\b",  # noqa: E501
            r"his \1",
            t,
        )
        t = re.sub(
            r"(?i) her(?!'t|self|e\b)(?=\s+[A-Za-z])", " his", t
        )
        t = re.sub(
            r"(?i) her(?!'t|self|e\b)(?=\s*[,!?.:;)\]]|\s*$)", " him", t
        )
        return t

    # Preserve ``` fences: only fix non-fence parts.
    parts = _split_preserve_fences(text)
    buf: list[str] = []
    for chunk, is_fence in parts:
        if is_fence:
            buf.append(chunk)
        else:
            lines: list[str] = []
            for line in chunk.splitlines(keepends=True):
                if line.endswith("\n"):
                    c, n = line[:-1], "\n"
                else:
                    c, n = line, ""
                lines.append(_one_line(c) + n)
            buf.append("".join(lines))
    return "".join(buf)


_RE_READ_ONLY_I_AM = re.compile(
    r"(?i)\bI\s+am\s+read[- ]only\b|\bI'?m\s+read[- ]only\b"
)
_RE_CANNOT_WRITE_FILES = re.compile(r"(?i)\bI\s+cannot\s+write\s+files\b")


def soften_capability_downgrade_phrases(text: str) -> str:
    """
    Reduce misleading identity fragments when web tools were used (read-only fetch/search).
    Does not change fenced code blocks (caller runs on already-clean segments paths).
    """
    if not text or not text.strip():
        return text
    t = _RE_READ_ONLY_I_AM.sub(
        "Nexa used read-only web tools only where sources are cited below",
        text,
    )
    t = _RE_CANNOT_WRITE_FILES.sub(
        "File writes here follow workspace approval policy — say what to change if you need a write",
        t,
    )
    return t


def finalize_user_facing_text(
    text: str, *, user_preferences: dict[str, str] | None = None
) -> str:
    from app.services.memory_preferences import get_effective_owner_pronoun

    c = clean_response_formatting(text)
    c = soften_capability_downgrade_phrases(c)
    return _apply_owner_pronoun_fixes_prose(c, get_effective_owner_pronoun(user_preferences))


def clean_response_formatting(text: str) -> str:
    """
    Normalize common noisy list patterns; preserve fenced code blocks, ## headings, links,
    and most inline emphasis. Safe to run on final user-facing strings only.
    """
    if not text:
        return text
    parts = _split_preserve_fences(text)
    buf: list[str] = []
    for chunk, is_fence in parts:
        if is_fence:
            buf.append(chunk)
        else:
            buf.append(_clean_prose_segment(chunk))
    return "".join(buf)
