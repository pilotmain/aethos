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
        or "git push" in tl
        or re.search(r"\bpush\s+(changes|commits|to\s+origin)\b", tl)
    )
    railway = bool(re.search(r"\brailway\b", tl) or "railway.app" in url_blob or "railway.com" in url_blob)

    intent: dict[str, Any] = {
        "vercel_deploy": vercel_deploy,
        "github_push": github_push,
        "railway": railway,
        "exact_request": raw,
    }
    if vercel_deploy and not railway:
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
    if not (fi.get("vercel_deploy") or fi.get("github_push")):
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
    return b


__all__ = [
    "apply_focus_discipline_to_operator_execution_text",
    "extract_focused_intent",
]
