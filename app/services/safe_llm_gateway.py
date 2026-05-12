# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Safe path for text sent to external LLM providers: sanitize, minimize, optional file allowlist.

External LLM providers should not be called with raw PII, secrets, or unbounded context from
feature code. Prefer :func:`safe_llm_json_call` and :func:`safe_llm_text_call` which wrap
``app.services.llm_service`` helpers.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Project root: app/services/safe_llm_gateway.py -> app -> repo
PROJECT_ROOT = Path(__file__).resolve().parents[2]

REDACTIONS = {
    "email": "[EMAIL]",
    "phone": "[PHONE]",
    "api_key": "[API_KEY]",
    "password": "[PASSWORD]",
    "token": "[TOKEN]",
    "secret": "[SECRET]",
    "ssh_key": "[SSH_KEY]",
    "address": "[ADDRESS]",
    "credit_card": "[CREDIT_CARD]",
}

# Order: API-key shapes before phone (or digit runs in sk-... are mistaken for phone numbers)
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[\w.\-+%]+@[\w.\-]+\.[A-Za-z]{2,}\b"), REDACTIONS["email"]),
    (re.compile(r"\bsk-ant-api\d{2}-[A-Za-z0-9_\-]{20,}\b"), REDACTIONS["api_key"]),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"), REDACTIONS["api_key"]),
    (re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_\-]{20,}\b"), REDACTIONS["api_key"]),
    (re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)"), REDACTIONS["phone"]),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"), REDACTIONS["token"]),
    (
        re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*([^\s]+)"),
        r"\1=[PASSWORD]",
    ),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|"
            r"refresh[_-]?token|auth[_-]?token|client[_-]?secret)\s*[:=]\s*([^\s]+)"
        ),
        r"\1=[SECRET]",
    ),
    (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), REDACTIONS["credit_card"]),
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
        ),
        REDACTIONS["ssh_key"],
    ),
]


def _csv_setting(value: str) -> list[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def sanitize_text(text: str) -> str:
    if not text:
        return ""
    s = get_settings()
    if not s.safe_llm_mode:
        return text
    sanitized = text
    for pattern, replacement in PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    sanitized = re.sub(r"\n{4,}", "\n\n\n", sanitized)
    return sanitized


def read_safe_system_memory_snapshot(max_chars_each: int = 6000):
    """Load soul.md + memory.md for prompts, with the same sanitization as other LLM-bound text."""
    from app.services.system_memory_files import SystemMemorySnapshot, read_system_memory_snapshot

    snapshot = read_system_memory_snapshot(max_chars_each=max_chars_each)
    return SystemMemorySnapshot(
        soul=sanitize_text(snapshot.soul),
        memory=sanitize_text(snapshot.memory),
    )


def is_safe_path(path: str | Path) -> bool:
    p = Path(path)
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve()
    else:
        p = p.resolve()
    try:
        p.relative_to(PROJECT_ROOT)
    except ValueError:
        return False

    rel = str(p.relative_to(PROJECT_ROOT)).replace("\\", "/")
    settings = get_settings()
    allowed_roots = _csv_setting(settings.safe_llm_allowed_roots)
    blocked = _csv_setting(settings.safe_llm_blocked_patterns)

    if allowed_roots:
        if not any(
            rel == root or rel == root + "/" or rel.startswith(root + "/")
            for root in allowed_roots
        ):
            return False

    rel_parts = rel.split("/")
    for pattern in blocked:
        if not pattern:
            continue
        if pattern == ".env" or pattern.endswith("/.env"):
            if any(part == ".env" for part in rel_parts):
                return False
        elif pattern in rel:
            return False
    return True


def read_safe_file(path: str | Path, max_chars: int | None = None) -> str:
    if not is_safe_path(path):
        raise PermissionError(f"Blocked unsafe file path: {path}")
    max_chars = max_chars or get_settings().safe_llm_max_chars
    p = Path(path)
    if not p.is_absolute():
        p = (PROJECT_ROOT / p).resolve()
    with open(p, encoding="utf-8", errors="replace") as f:
        content = f.read(max_chars + 1)
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[TRUNCATED]"
    return sanitize_text(content)


def minimize_context(text: str, max_chars: int | None = None) -> str:
    max_chars = max_chars or get_settings().safe_llm_max_chars
    text = sanitize_text(text) if get_settings().safe_llm_mode else text
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.65)]
    tail = text[-int(max_chars * 0.25) :]
    return (
        head
        + "\n\n[...MIDDLE OMITTED FOR PRIVACY AND LENGTH...]\n\n"
        + tail
    )


def summarize_code_for_llm(path: str | Path, content: str) -> str:
    suffix = Path(path).suffix
    lines = content.splitlines()
    interesting: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("class ", "def ", "async def ")):
            interesting.append(stripped)
        elif stripped.startswith(("from ", "import ")):
            interesting.append(stripped)
        elif "TODO" in stripped or "FIXME" in stripped:
            interesting.append(stripped)
    summary = "\n".join(interesting[:120])
    return sanitize_text(
        f"File: {Path(path).name}\n"
        f"Type: {suffix}\n"
        f"Structural summary:\n{summary or '[no structure extracted]'}"
    )


def build_safe_context(
    *,
    user_request: str,
    extra_text: str | None = None,
    file_paths: list[str | Path] | None = None,
    include_raw_code: bool | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    include_raw_code = (
        settings.safe_llm_allow_raw_code
        if include_raw_code is None
        else include_raw_code
    )
    if not settings.safe_llm_mode:
        max_c = settings.safe_llm_max_chars
        parts: list[str] = ["User request:\n" + (user_request or "")]
        if extra_text:
            parts.append("Additional context:\n" + extra_text)
        for pth in file_paths or []:
            if not is_safe_path(pth):
                raise PermissionError(f"Blocked unsafe file path: {pth}")
            p = Path(pth)
            if not p.is_absolute():
                p = (PROJECT_ROOT / p).resolve()
            with open(p, encoding="utf-8", errors="replace") as f:
                c = f.read(max_c + 1)
            if len(c) > max_c:
                c = c[:max_c] + "\n\n[TRUNCATED]"
            parts.append(f"File: {pth}\n\n{c}")
        joined = "\n\n---\n\n".join(parts)
        return {
            "safe_context": joined,
            "redacted": False,
            "raw_code_included": include_raw_code,
        }

    context_parts: list[str] = [
        "User request:\n" + minimize_context(user_request, max_chars=1500)
    ]
    if extra_text:
        context_parts.append(
            "Additional context:\n" + minimize_context(extra_text, max_chars=2500)
        )
    for pth in file_paths or []:
        content = read_safe_file(pth)
        if include_raw_code:
            file_context = f"File: {pth}\n\n{content}"
        else:
            file_context = summarize_code_for_llm(pth, content)
        context_parts.append(file_context)
    safe_context = "\n\n---\n\n".join(context_parts)
    return {
        "safe_context": minimize_context(safe_context),
        "redacted": True,
        "raw_code_included": include_raw_code,
    }


def composer_context_to_safe_llm_payload(ctx: Any) -> dict[str, Any]:
    """
    Map :class:`app.services.response_composer.ResponseContext` to a payload for external LLM calls.
    Raw ``ctx`` fields are unchanged; this returns a new dict.
    """
    s = get_settings()
    p = ctx.to_payload()
    if not s.safe_llm_mode:
        return p
    p["user_message"] = minimize_context(
        sanitize_text(p.get("user_message") or ""), max_chars=1500
    )
    p["focus_task"] = (
        minimize_context(sanitize_text(p.get("focus_task") or ""), max_chars=800)
        if p.get("focus_task")
        else None
    )
    p["selected_tasks"] = [
        minimize_context(sanitize_text(t), max_chars=800)
        for t in (p.get("selected_tasks") or [])
    ]
    p["deferred_lines"] = [
        minimize_context(sanitize_text(t), max_chars=800)
        for t in (p.get("deferred_lines") or [])
    ]
    up = p.get("user_preferences") or {}
    p["user_preferences"] = {
        k: minimize_context(sanitize_text(str(v)), max_chars=400) for k, v in up.items()
    }
    p["planning_style"] = minimize_context(
        sanitize_text(str(p.get("planning_style") or "gentle")), max_chars=80
    )
    if p.get("detected_state") is not None:
        p["detected_state"] = minimize_context(
            sanitize_text(str(p["detected_state"])), max_chars=200
        )
    cc = p.get("conversation_context")
    if isinstance(cc, dict):
        rm = cc.get("recent_messages") or []
        safe_rm: list[dict] = []
        for m in rm[-6:] if isinstance(rm, list) else []:
            if not isinstance(m, dict):
                continue
            safe_rm.append(
                {
                    "role": m.get("role"),
                    "text": minimize_context(
                        sanitize_text(str(m.get("text") or "")),
                        max_chars=500,
                    ),
                }
            )
        p["conversation_context"] = {
            "active_topic": minimize_context(
                sanitize_text(str(cc.get("active_topic") or "")), max_chars=200
            )
            or None,
            "summary": minimize_context(
                sanitize_text(str(cc.get("summary") or "")), max_chars=800
            )
            or None,
            "recent_messages": safe_rm,
            "active_topic_confidence": float(cc.get("active_topic_confidence", 0.5) or 0.5),
            "manual_topic_override": bool(cc.get("manual_topic_override", False)),
        }
    return p


def safe_llm_json_call(
    *,
    system_prompt: str,
    user_request: str,
    extra_text: str | None = None,
    file_paths: list[str | Path] | None = None,
    schema_hint: str | None = None,
    db: Any | None = None,
    telegram_user_id: int | None = None,
) -> dict:
    if db is not None and telegram_user_id is not None:
        from app.services.llm_request_context import llm_telegram_context

        with llm_telegram_context(db, int(telegram_user_id)):
            return safe_llm_json_call(
                system_prompt=system_prompt,
                user_request=user_request,
                extra_text=extra_text,
                file_paths=file_paths,
                schema_hint=schema_hint,
            )
    from app.services.llm_service import call_primary_llm_json

    safe = build_safe_context(
        user_request=user_request,
        extra_text=extra_text,
        file_paths=file_paths,
    )
    _log_safe_meta(safe)
    sys_sanitized = (
        minimize_context(sanitize_text(system_prompt), max_chars=20000)
        if get_settings().safe_llm_mode
        else system_prompt
    )
    prompt = (
        sys_sanitized
        + "\n\nYou will receive sanitized/minimized context. "
        "Respect redaction markers like [EMAIL], [TOKEN], [SECRET]. Do not ask for secrets.\n\n"
        + safe["safe_context"]
    )
    if schema_hint:
        sh = (
            minimize_context(sanitize_text(schema_hint), max_chars=2000)
            if get_settings().safe_llm_mode
            else schema_hint
        )
        prompt += "\n\nReturn JSON with this shape:\n" + sh
    return call_primary_llm_json(prompt)


def safe_llm_text_call(
    *,
    system_prompt: str,
    user_request: str,
    extra_text: str | None = None,
    file_paths: list[str | Path] | None = None,
    db: Any | None = None,
    telegram_user_id: int | None = None,
) -> str:
    if db is not None and telegram_user_id is not None:
        from app.services.llm_request_context import llm_telegram_context

        with llm_telegram_context(db, int(telegram_user_id)):
            return safe_llm_text_call(
                system_prompt=system_prompt,
                user_request=user_request,
                extra_text=extra_text,
                file_paths=file_paths,
            )
    from app.services.llm_service import call_primary_llm_text

    safe = build_safe_context(
        user_request=user_request,
        extra_text=extra_text,
        file_paths=file_paths,
    )
    _log_safe_meta(safe)
    sys_sanitized = (
        minimize_context(sanitize_text(system_prompt), max_chars=20000)
        if get_settings().safe_llm_mode
        else system_prompt
    )
    prompt = (
        sys_sanitized
        + "\n\nYou will receive sanitized/minimized context. "
        "Respect redaction markers like [EMAIL], [TOKEN], [SECRET]. Do not ask for secrets.\n\n"
        + safe["safe_context"]
    )
    return call_primary_llm_text(prompt)


def _log_safe_meta(safe: dict[str, Any]) -> None:
    ctx = safe.get("safe_context") or ""
    logger.info(
        "safe_llm_call redacted=%s raw_code=%s len=%s",
        safe.get("redacted"),
        safe.get("raw_code_included"),
        len(ctx) if isinstance(ctx, str) else 0,
    )
