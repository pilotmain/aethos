"""
Ruthless focus on the user’s explicit ask — suppress unrelated provider noise in replies.

Used by operator / execution paths and the gateway finalizer so Vercel + GitHub turns
do not drag in Railway boilerplate unless the user mentioned Railway.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def extract_focused_intent(user_message: str) -> dict[str, Any]:
    """
    Return coarse flags for what the user actually named.

    ``ignore_railway`` is true when Vercel (or Vercel-like URL) is in scope and the user
    did not mention Railway — downstream paths should not default to Railway copy.
    """
    raw = (user_message or "").strip()
    tl = raw.lower()
    try:
        from app.services.provider_router import extract_urls_from_text

        url_blob = " ".join(extract_urls_from_text(raw)).lower()
    except Exception:  # noqa: BLE001
        url_blob = ""

    vercel_deploy = bool(
        re.search(r"\bvercel\b", tl)
        or "vercel.com" in tl
        or ".vercel.app" in tl
        or "vercel.app" in tl
        or "vercel.com" in url_blob
        or ".vercel.app" in url_blob
    )
    github_push = bool(
        re.search(r"\bgithub\b", tl)
        or "github.com" in tl
        or "github.com" in url_blob
        or "push to remote" in tl
        or "push change" in tl
        or "git push" in tl
        or re.search(r"\bpush\s+(changes|commits|to\s+origin)\b", tl)
    )
    # Local worktree / laptop wording — not a hosted deploy ask; still skip Railway defaults.
    local_git_workspace = bool(
        re.search(
            r"(?i)(check\s+this\s+git\s+in\s+local|this\s+git\s+in\s+local|git\s+in\s+local|"
            r"\blocal\s+git\b|on\s+my\s+machine|this\s+git\s+locally)",
            raw,
        )
    )
    aws_scope = bool(
        re.search(r"\baws\b", tl)
        or "amazonaws.com" in url_blob
        or "aws.amazon.com" in url_blob
    )
    railway = bool(re.search(r"\brailway\b", tl) or "railway.app" in url_blob or "railway.com" in url_blob)

    intent: dict[str, Any] = {
        "vercel_deploy": vercel_deploy,
        "github_push": github_push,
        "aws_scope": aws_scope,
        "railway": railway,
        "exact_request": raw,
        "local_git_workspace": local_git_workspace,
    }
    if (vercel_deploy or github_push or aws_scope or local_git_workspace) and not railway:
        intent["ignore_railway"] = True
    if railway and not vercel_deploy:
        intent["ignore_vercel_noise"] = True
    return intent


def _strip_lines_mentioning_railway_without_vercel(text: str) -> str:
    lines = (text or "").splitlines()
    out: list[str] = []
    for ln in lines:
        if re.search(r"\brailway\b", ln, re.I) and not re.search(r"\bvercel\b", ln, re.I):
            continue
        out.append(ln)
    joined = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", joined).strip()


def _squash_access_placeholder_wall(body: str, fi: dict[str, Any]) -> str:
    """Shorten generic “once access is in place” screeds when the ask is already Vercel/GitHub scoped."""
    if not body or len(body) < 600:
        return body
    if not (fi.get("vercel_deploy") or fi.get("github_push") or fi.get("aws_scope")):
        return body
    low = body.lower()
    if "once access is in place" not in low and "once access is available" not in low:
        return body
    return re.sub(
        r"(?is)[^\n]{0,320}(?:once access is in place|once access is available)[^\n]{0,320}(?:\n[\t ]*[^\n]+){0,10}",
        "\n\n_(Access details only if a step below fails without them.)_\n",
        body,
        count=1,
    )


def apply_focus_discipline_to_operator_execution_text(body: str, *, user_text: str) -> str:
    """Strip unrelated Railway lines and compress access placeholder walls."""
    fi = extract_focused_intent(user_text)
    b = body or ""
    if fi.get("ignore_railway"):
        before = len(b)
        b = _strip_lines_mentioning_railway_without_vercel(b)
        if len(b) < before:
            logger.info(
                "intent_focus_filter.stripped_railway_lines chars=%s->%s",
                before,
                len(b),
            )
    b = _squash_access_placeholder_wall(b, fi)
    b = strip_unrelated_providers_from_reply(b, user_text=user_text)
    return b


def strip_unrelated_providers_from_reply(body: str, *, user_text: str) -> str:
    """
    Drop lines that hawk a host provider the user did not ask for (router-driven).

    Preserves code fences and does not shrink already-focused short replies.
    """
    if not (body or "").strip() or "```" in body:
        return body
    try:
        from app.services.provider_router import detect_primary_provider, extract_urls_from_text
    except Exception:  # noqa: BLE001
        return body
    prov, conf = detect_primary_provider(user_text, extract_urls_from_text(user_text))
    if prov == "generic" or conf < 0.25:
        return body
    u = (user_text or "").lower()
    lines = body.splitlines()
    out: list[str] = []
    for ln in lines:
        low = ln.lower()
        if prov != "railway" and "railway" not in u and re.search(r"\brailway\b", low):
            continue
        if prov != "vercel" and "vercel" not in u and ".vercel.app" not in u and re.search(r"\bvercel\b", low):
            continue
        if prov != "github" and "github" not in u and re.search(r"\bgithub\b", low):
            continue
        if prov != "aws" and not re.search(r"\baws\b", u) and re.search(r"\baws\b", low):
            continue
        out.append(ln)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def apply_operator_zero_nag_surface(text: str) -> str:
    """
    Strip repetitive access/setup boilerplate from operator / execution-loop replies.

    Does not alter secret-handling blocks; run after focus discipline on gateway-bound text only.
    """
    if not (text or "").strip():
        return text
    out = text
    for lit in (
        "once access is in place",
        "once access is available",
        "report findings first",
        "host executor",
        "nexa_host_executor_enabled",
    ):
        out = re.sub(re.escape(lit), " ", out, flags=re.I)
    out = re.sub(r"(?is)right now i don'?t have enough[^\n]*", " ", out)
    out = re.sub(r"(?is)register a repo path[^\n]{0,200}", " ", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    if len(out) < 12:
        return "Running autonomous checks for your request on this worker now."
    return out


def operator_precise_short_enabled() -> bool:
    """True when operator mode wants compact prose (fenced command blocks preserved elsewhere)."""
    try:
        from app.core.config import get_settings

        s = get_settings()
        return bool(getattr(s, "nexa_operator_mode", False)) and bool(
            getattr(s, "nexa_operator_precise_short_responses", True)
        )
    except Exception:  # noqa: BLE001
        return False


def _user_assumes_cli_ready(user_text: str) -> bool:
    t = (user_text or "").lower()
    return any(
        x in t
        for x in (
            "everything installed",
            "cli installed",
            "have the cli",
            "have everything",
            "already installed",
            "all tools installed",
        )
    )


_PRECISE_DROP_SUBSTRINGS = (
    "read-only diagnostics",
    "read-only —",
    "i will inspect",
    "i'll inspect",
    "progress and command output",
    "only where your host flags",
    "real blockers with evidence",
    "diagnostics only on this turn",
    "full evidence is in the logs",
    "command output in sections above",
    "mission complete.",
    "no deploy or git write",
    "no pr or push performed",
)

_CLI_ASSUME_DROP_SUBSTRINGS = (
    "cli is not installed",
    "cli missing",
    "not available in path",
    "skipped — vercel cli",
    "_vercel cli is not",
    "`vercel` not found in path",
    "`gh` not found in path",
    "not found in path. run `which vercel`",
    "not found in path. run `which gh`",
)


def clean_operator_reply_format(body: str) -> str:
    """Drop markdown HR clutter and excessive blank lines from operator/execution replies."""
    if not (body or "").strip():
        return body
    lines: list[str] = []
    for ln in body.splitlines():
        if ln.strip() == "---":
            continue
        lines.append(ln)
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def apply_precise_operator_response(body: str, *, user_text: str) -> str:
    """
    Collapse verbose operator/execution prose; preserve ``` fenced blocks (CLI stdout/stderr).

    Does not remove factual phase ``` blocks or markdown tables inside fences.
    """
    if not operator_precise_short_enabled() or not (body or "").strip():
        return body
    assume_cli = _user_assumes_cli_ready(user_text)
    raw = body
    raw = re.sub(r"(?is)^### Live progress\b[^\n]*\n[\s\S]*?(?=\n---|\n### |\Z)", "", raw)
    raw = re.sub(r"(?is)^### Progress\b[^\n]*\n(?:→[^\n]*\n)+(?=\n---|\n### |\Z)", "→ Running checks…\n\n", raw, count=1)
    parts = re.split(r"(```[\s\S]*?```)", raw)
    out: list[str] = []
    for seg in parts:
        if seg.startswith("```"):
            out.append(seg)
            continue
        lines: list[str] = []
        for ln in seg.splitlines():
            st = ln.strip()
            if not st:
                lines.append("")
                continue
            low = ln.lower()
            if any(b in low for b in _PRECISE_DROP_SUBSTRINGS):
                continue
            if assume_cli and any(b in low for b in _CLI_ASSUME_DROP_SUBSTRINGS):
                continue
            lines.append(ln)
        chunk = "\n".join(lines)
        chunk = re.sub(r"\n{3,}", "\n\n", chunk).strip()
        out.append(chunk)
    rebuilt: list[str] = []
    for seg in out:
        if seg.startswith("```"):
            rebuilt.append(seg)
        elif seg.strip():
            rebuilt.append(seg.strip())
    merged = "\n\n".join(rebuilt)
    merged = re.sub(r"\n{3,}", "\n\n", merged).strip()
    if len(merged) < 8:
        return body
    return merged


__all__ = [
    "apply_focus_discipline_to_operator_execution_text",
    "apply_operator_zero_nag_surface",
    "apply_precise_operator_response",
    "clean_operator_reply_format",
    "extract_focused_intent",
    "operator_precise_short_enabled",
    "strip_unrelated_providers_from_reply",
]
