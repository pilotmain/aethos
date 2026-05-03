"""
End-to-end operator orchestration entry (read-only diagnostics first).

Runs when ``NEXA_OPERATOR_MODE`` is enabled and the user message looks like an
operator task (provider cues, workspace path, deploy/fix language).

Railway-only turns remain in :mod:`app.services.execution_loop` to avoid duplicate
bounded runs unless combined with other providers in the same message.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.core.config import get_settings

if TYPE_CHECKING:
    from app.services.gateway.context import GatewayContext

logger = logging.getLogger(__name__)


@dataclass
class OperatorExecutionResult:
    handled: bool
    text: str
    provider: str | None = None
    ran: bool = False
    verified: bool = False
    blocker: str | None = None
    progress: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


def _extract_workspace_path(text: str) -> str | None:
    m = re.search(r"(?i)workspace\s*:\s*(\S+)", text or "")
    if not m:
        return None
    p = m.group(1).strip().strip("`\"'")
    return p or None


def _workspace_for_phases(db: Session, uid: str, path_from_message: str | None) -> str | None:
    if path_from_message and str(path_from_message).strip():
        return str(path_from_message).strip()
    from app.services.dev_runtime.workspace import list_workspaces

    rows = list_workspaces(db, uid)
    if len(rows) != 1:
        return None
    p = str(getattr(rows[0], "repo_path", "") or "").strip()
    return p or None


def _wants_phase_keywords(raw: str) -> bool:
    return bool(
        re.search(
            r"(?i)\b(test|tests|pytest|npm test|commit|push|deploy|verify|patch)\b",
            raw or "",
        )
    )


def _phase_result_markdown(title: str, r: dict[str, Any]) -> str:
    lines = [f"### {title}", ""]
    if r.get("ok"):
        lines.append("**Result:** ok")
    else:
        err = r.get("error") or r.get("stderr") or "unknown"
        lines.append(f"**Result:** failed — `{str(err)[:500]}`")
    if r.get("stdout"):
        lines.extend(["", "```", str(r["stdout"])[:6000], "```"])
    if r.get("commit_sha"):
        lines.append(f"**Commit SHA:** `{r['commit_sha']}`")
    if r.get("status_code") is not None:
        lines.append(f"**HTTP:** `{r['status_code']}` for `{r.get('url', '')}`")
    return "\n".join(lines)


def _append_operator_phases(
    *,
    raw: str,
    db: Session,
    uid: str,
    ws_hint: str | None,
    vercel_cue: bool,
    railway_cue: bool,
) -> tuple[list[str], dict[str, Any], list[str]]:
    """Run gated test / commit / push / deploy / verify phases. Returns (sections, evidence, progress)."""
    ws = _workspace_for_phases(db, uid, ws_hint)
    if not ws or not _wants_phase_keywords(raw):
        return [], [], []

    from app.services.operator_execution_actions import (
        commit_and_push,
        deploy_railway,
        deploy_vercel,
        extract_production_url,
        run_tests,
        verify_http_head,
    )

    sections: list[str] = []
    ev: dict[str, Any] = {}
    prog: list[str] = []

    if re.search(r"(?i)\b(test|tests|pytest|npm test)\b", raw):
        prog.append("Running tests")
        tr = run_tests(ws)
        ev["tests"] = tr
        sections.append(_phase_result_markdown("Phase: test", tr))

    if (re.search(r"(?i)\bcommit\b", raw) and re.search(r"(?i)\bpush\b", raw)) or re.search(
        r"(?i)push\s+changes", raw
    ):
        prog.append("Committing and pushing")
        cp = commit_and_push(ws, "operator: automated checkpoint")
        ev["commit_push"] = cp
        sections.append(_phase_result_markdown("Phase: commit + push", cp))

    if vercel_cue and re.search(r"\bdeploy\b", raw, re.I):
        prog.append("Deploying to Vercel (production)")
        dv = deploy_vercel(ws)
        ev["deploy_vercel"] = dv
        sections.append(_phase_result_markdown("Phase: deploy (Vercel)", dv))

    if railway_cue and re.search(r"\b(deploy|railway up)\b", raw, re.I):
        prog.append("Deploying via Railway")
        dr = deploy_railway(ws)
        ev["deploy_railway"] = dr
        sections.append(_phase_result_markdown("Phase: deploy (Railway)", dr))

    url = extract_production_url(raw)
    if url and re.search(r"\bverify\b", raw, re.I):
        prog.append("Verifying production URL")
        vh = verify_http_head(url)
        ev["verify"] = vh
        sections.append(_phase_result_markdown("Phase: verify", vh))

    return sections, ev, prog


def try_operator_execution(
    *,
    user_text: str,
    gctx: GatewayContext,
    db: Session,
    snapshot: dict[str, Any] | None = None,
) -> OperatorExecutionResult:
    """
    Deterministic provider diagnostics before generic chat. Returns ``handled=False`` when skipped.
    """
    uid = (gctx.user_id or "").strip()
    raw = (user_text or "").strip()
    if not uid or not raw:
        return OperatorExecutionResult(handled=False, text="")

    settings = get_settings()
    if not bool(getattr(settings, "nexa_operator_mode", False)):
        return OperatorExecutionResult(handled=False, text="")

    from app.services.external_execution_session import is_retry_external_execution
    from app.services.operator_runners.base import (
        detect_provider_hints,
        forbid_unverified_success_language,
        format_operator_progress,
    )
    from app.services.operator_runners.github import run_github_operator_readonly
    from app.services.operator_runners.local_dev import run_git_status_at_path, run_local_git_status
    from app.services.operator_runners.vercel import run_vercel_operator_readonly

    # Retry/resume fragments stay on execution_loop / external_execution_session.
    if is_retry_external_execution(raw):
        return OperatorExecutionResult(handled=False, text="")

    hints = detect_provider_hints(raw)
    ws_path = _extract_workspace_path(raw)

    vercel_cue = hints["vercel"]
    gh_cue = hints["github"]
    railway_cue = hints["railway"]

    ws_resolved = ws_path or _workspace_for_phases(db, uid, None)
    phase_only = bool(ws_resolved and _wants_phase_keywords(raw) and not (vercel_cue or gh_cue or ws_path))

    # Railway-only diagnostics stay on execution_loop unless phase keywords need this path.
    if railway_cue and not vercel_cue and not gh_cue and not ws_path and not phase_only:
        return OperatorExecutionResult(handled=False, text="")

    if not (vercel_cue or gh_cue or ws_path or phase_only):
        return OperatorExecutionResult(handled=False, text="")

    sections: list[str] = []
    evidence: dict[str, Any] = {}
    progress: list[str] = []
    verified_any = False
    primary_provider: str | None = None

    cwd = ws_path if ws_path else None

    if vercel_cue:
        primary_provider = primary_provider or "vercel"
        body_v, ev_v, prog_v, v_ok = run_vercel_operator_readonly(cwd=cwd)
        sections.append(body_v)
        evidence["vercel"] = ev_v
        progress.extend(prog_v)
        verified_any = verified_any or v_ok

    if gh_cue:
        primary_provider = primary_provider or "github"
        body_g, ev_g, prog_g, g_ok = run_github_operator_readonly(cwd=cwd)
        sections.append(body_g)
        evidence["github"] = ev_g
        progress.extend(prog_g)
        verified_any = verified_any or g_ok

    if ws_path:
        primary_provider = primary_provider or "local_dev"
        body_l, ev_l, prog_l, l_ok = run_git_status_at_path(ws_path)
        sections.append(body_l)
        evidence["local_dev"] = ev_l
        progress.extend(prog_l)
        verified_any = verified_any or l_ok
    elif hints["local_git"] and not vercel_cue and not gh_cue:
        primary_provider = primary_provider or "local_dev"
        body_l, ev_l, prog_l, l_ok = run_local_git_status(db, uid)
        sections.append(body_l)
        evidence["local_dev"] = ev_l
        progress.extend(prog_l)
        verified_any = verified_any or l_ok

    if phase_only and not sections:
        primary_provider = primary_provider or "local_dev"
        body_l, ev_l, prog_l, l_ok = run_local_git_status(db, uid)
        sections.append(body_l)
        evidence["local_dev"] = ev_l
        progress.extend(prog_l)
        verified_any = verified_any or l_ok

    ws_patch = ws_path or ws_resolved
    if ws_patch and "```diff" in raw.lower():
        from app.services.operator_execution_actions import apply_code_fix

        m = re.search(r"```diff\s*\n(.*?)```", raw, re.S | re.I)
        if m:
            progress.append("Applying embedded unified diff")
            ap = apply_code_fix(ws_patch, m.group(1).strip())
            evidence["patch"] = ap
            sections.append(_phase_result_markdown("Phase: fix (patch)", ap))
            verified_any = verified_any or bool(ap.get("ok"))

    phase_secs, phase_ev, phase_prog = _append_operator_phases(
        raw=raw, db=db, uid=uid, ws_hint=ws_path, vercel_cue=vercel_cue, railway_cue=railway_cue
    )
    if phase_secs:
        sections.extend(phase_secs)
        evidence["phases"] = phase_ev
        progress.extend(phase_prog)
        for v in phase_ev.values():
            if isinstance(v, dict) and v.get("ok"):
                verified_any = True
                break

    if not sections:
        return OperatorExecutionResult(handled=False, text="")

    merged = "\n\n---\n\n".join(sections)

    from app.services.operator_pulse import format_pulse_section, read_pulse_standing_orders

    pulse = read_pulse_standing_orders(ws_resolved)
    if pulse:
        merged = merged + "\n\n---\n\n" + format_pulse_section(pulse)

    merged = forbid_unverified_success_language(verified=verified_any, body=merged)

    if not any(x in merged for x in ("### Progress", "→ ")):
        merged = format_operator_progress(progress or ["Starting operator diagnostics"]) + "\n\n---\n\n" + merged

    logger.info(
        "operator_execution uid=%s providers=%s verified_any=%s",
        uid,
        list(evidence.keys()),
        verified_any,
    )

    return OperatorExecutionResult(
        handled=True,
        text=merged,
        provider=primary_provider,
        ran=True,
        verified=verified_any,
        blocker=None if verified_any else "diagnostic_only",
        progress=progress,
        evidence=evidence,
    )


__all__ = ["OperatorExecutionResult", "try_operator_execution"]
