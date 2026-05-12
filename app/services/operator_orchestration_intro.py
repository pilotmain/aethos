# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
OpenClaw-style proactive copy when operator mode is on (enhanced orchestration slice).

Prepends a short “mission accepted” block so the first reply feels alive, without
replacing deterministic CLI output or evidence blocks.
"""

from __future__ import annotations

import re

from app.core.config import get_settings


def _mission_summary(user_text: str, *, max_len: int = 160) -> str:
    t = re.sub(r"\s+", " ", (user_text or "").strip())
    if not t:
        return "this request"
    return t[:max_len] + ("…" if len(t) > max_len else "")


def maybe_prepend_operator_orchestration_intro(
    body: str,
    *,
    user_text: str,
    orchestration_source: str,
) -> str:
    """
    If ``NEXA_OPERATOR_MODE`` is on and proactive intro is enabled, prepend the
    standard operator preamble when ``body`` does not already include it.

    ``orchestration_source`` is ``operator_execution`` or ``execution_loop`` for logs only.
    """
    _ = orchestration_source
    s = get_settings()
    if not bool(getattr(s, "nexa_operator_mode", False)):
        return body
    if bool(getattr(s, "nexa_operator_precise_short_responses", True)):
        return body
    if not bool(getattr(s, "nexa_operator_proactive_intro", True)):
        return body
    b = (body or "").strip()
    if not b:
        return b
    if "**Understood.**" in b or "Entering operator run" in b:
        return body
    summary = _mission_summary(user_text)
    intro = (
        "**Understood.** Entering an **operator-style run** for: "
        f"_{summary}_\n\n"
        "I will **inspect → diagnose → fix → test → commit → push → deploy → verify** "
        "only where your host flags and allowlists permit (writes/deploys stay gated). "
        "Progress and command output are below; I stop on **real blockers** with evidence.\n\n"
        "---\n\n"
    )
    return intro + b


__all__ = ["maybe_prepend_operator_orchestration_intro"]
