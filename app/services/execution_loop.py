"""
Central execution loop router — bounded real work before generic LLM guidance (P0).

Product rule: attempt safe bounded actions or return exact technical blockers with mandatory progress.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.services.gateway.context import GatewayContext

logger = logging.getLogger(__name__)


@dataclass
class ExecutionLoopResult:
    handled: bool
    text: str
    ran: bool = False
    blocker: str | None = None
    progress: list[str] = field(default_factory=list)
    verified: bool = False


def _markdown_progress(lines: list[str]) -> str:
    body = "\n".join(f"→ {x}" for x in lines)
    return f"### Progress\n\n{body}"


def _ensure_progress_prefix(text: str, fallback_progress: list[str]) -> str:
    t = (text or "").strip()
    if "### Progress" in t or "→ Starting investigation" in t:
        return t
    if not fallback_progress:
        return t
    return f"{_markdown_progress(fallback_progress)}\n\n---\n\n{t}"


def _strong_hosted_or_deploy_cue(text: str) -> bool:
    tl = (text or "").lower()
    if re.search(
        r"(?i)\b(railway|render\.com|fly\.io|heroku|vercel|netlify)\b",
        tl,
    ):
        return True
    if re.search(
        r"(?i)\b(deploy|redeploy|production|hosted|service failing|check logs|fix repo|push changes)\b",
        tl,
    ):
        return True
    if re.search(r"https?://", tl):
        return True
    return False


def _execution_loop_applies(raw: str, snapshot: dict[str, Any] | None) -> bool:
    """True when this turn should use bounded external execution instead of generic chat."""
    from app.services.external_execution_session import is_retry_external_execution
    from app.services.intent_classifier import looks_like_external_execution, looks_like_external_investigation

    r = (raw or "").strip()
    if not r:
        return False
    if is_retry_external_execution(r):
        return True
    if looks_like_external_execution(r):
        return True
    if looks_like_external_investigation(r, snapshot):
        return _strong_hosted_or_deploy_cue(r)
    return False


def _synthetic_blocker_progress_for_access(*, reason: str) -> list[str]:
    base = [
        "Starting investigation",
        "Checking Railway access",
        "Checking local workspace",
    ]
    base.append(f"Stopped: {reason}")
    return base


def try_execute_or_explain(
    *,
    user_text: str,
    gctx: GatewayContext,
    db: Session,
    snapshot: dict[str, Any] | None = None,
) -> ExecutionLoopResult:
    """
    Attempt bounded external execution (Railway-style) or return exact blockers.

    Returns ``handled=False`` when this router does not apply — caller continues to LLM/missions.
    """
    uid = (gctx.user_id or "").strip()
    raw = (user_text or "").strip()
    if not uid or not raw:
        return ExecutionLoopResult(handled=False, text="")

    from app.services.conversation_context_service import get_or_create_context
    from app.services.external_execution_session import (
        is_retry_external_execution,
        maybe_start_external_probe_from_turn,
        try_resume_external_execution_turn,
        try_retry_external_execution_turn,
    )

    cctx = get_or_create_context(db, uid)
    snap = snapshot if isinstance(snapshot, dict) else {}

    # --- Explicit retry phrases (must run runner or exact blocker; never idle loop)
    if is_retry_external_execution(raw):
        out = try_retry_external_execution_turn(db, uid, raw, cctx)
        if out is not None:
            t = str(out.get("text") or "").strip()
            fb = ["Starting investigation", "Checking Railway access"]
            if "### Progress" not in t:
                t = _ensure_progress_prefix(t, fb)
            ran = "retrying railway investigation" in t.lower() or "verified checks" in t.lower()
            return ExecutionLoopResult(
                handled=True,
                text=t,
                ran=ran,
                blocker=None,
                progress=[],
                verified="verified checks" in t.lower(),
            )

    # --- Resume prefs / follow-up for external_execution fragment
    _resume = try_resume_external_execution_turn(db, uid, raw, cctx)
    if _resume is not None:
        t = str(_resume.get("text") or "").strip()
        if not t:
            t = (
                "Got it — I’ve recorded your deploy/hosted preferences.\n\n"
                "Send **retry external execution** to run read-only checks on this worker with fresh progress "
                "and output—or describe the next error in one line."
            )
        t = _ensure_progress_prefix(
            t,
            ["Starting investigation", "Recording deploy/hosted preferences"],
        )
        return ExecutionLoopResult(handled=True, text=t, ran=False, progress=[])

    # --- Direct probe (local CLI auth + probe markers)
    out = maybe_start_external_probe_from_turn(db, uid, raw, cctx, conversation_snapshot=snap)
    if out is not None:
        t = str(out.get("text") or "").strip()
        t = _ensure_progress_prefix(t, ["Starting investigation", "Running read-only Railway diagnostics"])
        return ExecutionLoopResult(handled=True, text=t, ran=True, progress=[])

    applies = _execution_loop_applies(raw, snap)
    if not applies:
        from app.core.config import get_settings

        if bool(getattr(get_settings(), "nexa_operator_mode", False)):
            from app.services.intent_classifier import looks_like_external_execution

            applies = looks_like_external_execution(raw)
    if not applies:
        return ExecutionLoopResult(handled=False, text="")

    from app.services.intent_focus_filter import extract_focused_intent
    from app.services.provider_router import should_skip_railway_bounded_path

    if extract_focused_intent(raw).get("ignore_railway") or should_skip_railway_bounded_path(raw):
        logger.info(
            "execution_loop.skip_railway_bounded_path uid=%s (focused_intent or vercel-dominant)",
            uid,
        )
        return ExecutionLoopResult(handled=False, text="")

    # --- Bounded runner path (same safe commands as external_execution_runner)
    from app.services.external_execution_access import (
        assess_external_execution_access,
        format_external_execution_access_reply,
        should_gate_external_execution,
    )
    from app.services.external_execution_runner import (
        format_investigation_for_chat,
        run_bounded_railway_repo_investigation,
    )

    access = assess_external_execution_access(db, uid)

    if should_gate_external_execution(raw, access):
        prog = ["Starting investigation", "Checking Railway access", "Checking local workspace"]
        if not access.dev_workspace_registered:
            prog.append("Stopped: no registered local workspace/repo path")
        elif not getattr(access, "host_executor_enabled", False):
            prog.append("Stopped: host executor disabled")
        elif access.railway_access_available is False:
            prog.append("Stopped: Railway access not available on this worker (no env token / no CLI)")
        else:
            prog.append("Stopped: access gate (see items below)")
        gate_body = format_external_execution_access_reply(access, user_text=raw)
        text_out = f"{_markdown_progress(prog)}\n\n---\n\n{gate_body}"
        blk = "access_gate"
        if not access.dev_workspace_registered:
            blk = "no_workspace"
        elif not access.railway_access_available:
            blk = "no_railway_access"
        return ExecutionLoopResult(
            handled=True,
            text=text_out,
            ran=False,
            blocker=blk,
            progress=prog,
            verified=False,
        )

    collected: dict[str, object] = {
        "deploy_mode": "report_then_approve",
        "permission_to_probe": True,
        "auth_method": "token_env" if access.railway_token_present else "local_cli",
    }
    inv = run_bounded_railway_repo_investigation(db, uid, collected)
    body = format_investigation_for_chat(inv)
    return ExecutionLoopResult(
        handled=True,
        text=body,
        ran=inv.skipped_reason is None,
        blocker=inv.skipped_reason,
        progress=list(inv.progress_lines),
        verified=inv.any_command_ok(),
    )


def run_deterministic_steps(
    steps: list[dict[str, Any]],
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Minimal synchronous multi-step runner (light NexaForge / Lobster-style slice).

    Each step is a dict with ``id`` (optional), ``tool`` (required), and optional ``args``.

    - ``noop`` — succeeds immediately.
    - ``echo`` — returns ``args["message"]`` in the result.
    - ``vercel_deploy`` / ``railway_deploy`` / ``deploy`` — unless
      ``context["operator_deploy_allowed"]`` is true, stops with
      ``status: approval_needed`` and ``token`` set to the step id.

    Unknown tools yield ``ok: False`` with ``error: unknown_tool`` for that step only.
    """
    ctx = context if isinstance(context, dict) else {}
    results: dict[str, Any] = {}
    deploy_like = frozenset({"vercel_deploy", "railway_deploy", "deploy"})
    for step in steps:
        if not isinstance(step, dict):
            continue
        sid = str(step.get("id") or "step")
        tool = str(step.get("tool") or "").strip()
        args = step.get("args") if isinstance(step.get("args"), dict) else {}
        if tool in deploy_like:
            if ctx.get("operator_deploy_allowed") is True:
                results[sid] = {"ok": True, "tool": tool, "simulated": True}
            else:
                return {
                    "status": "approval_needed",
                    "token": sid,
                    "results": results,
                    "pending": tool,
                }
            continue
        if tool == "noop":
            results[sid] = {"ok": True, "tool": tool}
        elif tool == "echo":
            results[sid] = {"ok": True, "tool": tool, "message": args.get("message", "")}
        else:
            results[sid] = {"ok": False, "error": "unknown_tool", "tool": tool}
    return {"status": "complete", "results": results}


__all__ = ["ExecutionLoopResult", "run_deterministic_steps", "try_execute_or_explain"]
