"""
End-to-end operator orchestration entry (read-only diagnostics first).

Runs when ``NEXA_OPERATOR_MODE`` is enabled and the user message looks like an
operator task (provider cues, workspace path, deploy/fix language).

With ``nexa_operator_zero_nag`` (default on), the gateway finalizer strips repetitive
access/setup boilerplate from operator and execution-loop replies.

Bounded Railway CLI probes may inject a session-cached ``RAILWAY_TOKEN`` from
:mod:`app.services.credential_session_store` when the worker env lacks one (never echoed).

Vercel/GitHub CLI subprocesses use :func:`app.services.operator_cli_path.cli_environ_for_operator`
and (when enabled) :func:`app.services.operator_shell_cli.run_allowlisted_argv_via_login_shell`
so ``nvm.sh`` and shell rc files apply like your login terminal.

Railway-only turns remain in :mod:`app.services.execution_loop` to avoid duplicate
bounded runs unless combined with other providers in the same message.
"""

from __future__ import annotations

import logging
import re
import time
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


def _strip_workspace_clause(text: str) -> str:
    """Remove ``Workspace: <path>`` so temp dirs (e.g. ``…/pytest-12/…``) do not trigger phase keywords."""
    return re.sub(r"(?i)workspace\s*:\s*\S+", "", text or "")


def _wants_phase_keywords(raw: str) -> bool:
    """Detect mutating / verify phase intent from user text (path-stripped)."""
    t = _strip_workspace_clause(raw)
    return bool(
        re.search(
            r"(?i)\b(test|tests|pytest|npm test|commit|push|deploy|verify|patch)\b",
            t,
        )
    )


def _format_live_progress_steps(lines: list[str]) -> str:
    trimmed = [str(x).strip() for x in lines if x and str(x).strip()]
    if not trimmed:
        return ""
    body = "\n".join(f"→ {x}" for x in trimmed)
    return f"### Live progress\n\n{body}"


def _precise_short_enabled() -> bool:
    try:
        from app.services.intent_focus_filter import operator_precise_short_enabled

        return operator_precise_short_enabled()
    except Exception:  # noqa: BLE001
        return False


def _format_live_progress_precise(provider: str | None) -> str:
    p = (provider or "operator").strip() or "operator"
    return f"→ **{p}**: running checks…"


def _http_verify_strict_ok(ver: Any) -> bool:
    if not isinstance(ver, dict) or not ver.get("ok"):
        return False
    try:
        sc = int(ver.get("status_code") or 0)
    except (TypeError, ValueError):
        return False
    return 200 <= sc < 300


def _compute_strict_operator_verified(evidence: dict[str, Any], runner_ok: bool) -> bool:
    """
    True only when runner diagnostics succeeded (if any) **and** every phase succeeded
    with deploy+HTTP follow-up when a production deploy was executed (not skipped).
    """
    if not runner_ok:
        return False
    phases = evidence.get("phases")
    if not isinstance(phases, dict) or not phases:
        return True
    for v in phases.values():
        if not isinstance(v, dict) or not v.get("ok"):
            return False
    dv = phases.get("deploy_vercel")
    dr = phases.get("deploy_railway")
    if isinstance(dv, dict) and dv.get("ok") and not dv.get("noop"):
        if not _http_verify_strict_ok(phases.get("verify")):
            return False
    if isinstance(dr, dict) and dr.get("ok") and not dr.get("noop"):
        if not _http_verify_strict_ok(phases.get("verify")):
            return False
    return True


def _append_verified_mission_footer(text: str, *, strict_verified: bool, evidence: dict[str, Any]) -> str:
    if _precise_short_enabled():
        # Avoid a standalone "Verified." line — progress + phases carry proof.
        return text
    if not strict_verified or not (text or "").strip():
        return text
    phases = evidence.get("phases")
    ver: Any = None
    if isinstance(phases, dict):
        ver = phases.get("verify")
    sc: int | None = None
    if isinstance(ver, dict) and ver.get("status_code") is not None:
        try:
            sc = int(ver["status_code"])
        except (TypeError, ValueError):
            sc = None
    sha = ""
    if isinstance(phases, dict):
        cp = phases.get("commit_push")
        if isinstance(cp, dict) and cp.get("commit_sha"):
            sha = str(cp["commit_sha"])[:12]
    bits: list[str] = []
    if sc is not None:
        bits.append(f"HTTP `{sc}` from production verify")
    if sha:
        bits.append(f"last pushed commit `{sha}`")
    proof = "; ".join(bits) if bits else "command output in sections above"
    return (
        text.rstrip()
        + "\n\n---\n\n**Mission complete.** Verified: "
        + proof
        + ". Full evidence is in the logs and phase blocks above."
    )


def _try_enqueue_readme_push_chain_after_github(
    db: Session,
    uid: str,
    user_text: str,
    gctx: "GatewayContext",
) -> str | None:
    """
    After successful ``gh`` verification, if the user asked for a README+push style mutation,
    enqueue the same NL chain the host-executor chat path would use.
    """
    if not (user_text or "").strip() or not (uid or "").strip():
        return None
    s = get_settings()
    if not bool(getattr(s, "nexa_host_executor_enabled", False)):
        return None
    if not bool(getattr(s, "nexa_host_executor_chain_enabled", False)):
        return None

    from app.services.host_executor_chat import _validate_enqueue_payload, enqueue_host_job_from_validated_payload
    from app.services.host_executor_intent import title_for_payload
    from app.services.host_executor_nl_chain import try_infer_readme_push_chain_nl

    pl = try_infer_readme_push_chain_nl(user_text)
    if not pl:
        return None
    safe = _validate_enqueue_payload(pl)
    if not safe:
        return None

    from app.services.host_executor import execute_payload
    from app.services.sub_agent_audit import log_agent_event
    from app.services.sub_agent_auto_approve import get_auto_approve_message, should_auto_approve
    from app.services.sub_agent_router import orchestration_chat_key

    chat_key = orchestration_chat_key(gctx)
    aa_ok, aa_reason = should_auto_approve(chat_key, "git", agent=None)
    actions = safe.get("actions") if (safe.get("host_action") or "").strip().lower() == "chain" else None
    n = len(actions) if isinstance(actions, list) else 1

    if aa_ok:
        t0 = time.perf_counter()
        try:
            out = execute_payload(safe)
        except ValueError as exc:
            log_agent_event(
                "auto_approved_execute",
                domain="git",
                chat_id=chat_key,
                user_id=uid.strip(),
                success=False,
                error=str(exc)[:2000],
                duration_ms=(time.perf_counter() - t0) * 1000.0,
                extra={"source": "operator_readme_chain", "reason": aa_reason},
            )
            return f"❌ Auto-execution failed: {exc}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("operator auto-approved readme chain failed: %s", exc, exc_info=False)
            return f"❌ Auto-execution error: {exc}"
        log_agent_event(
            "auto_approved_execute",
            domain="git",
            chat_id=chat_key,
            user_id=uid.strip(),
            action="readme_push_chain",
            success=True,
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            extra={"source": "operator_readme_chain", "reason": aa_reason},
        )
        head = get_auto_approve_message("git", n)
        body = (out or "").strip()
        return f"{head}\n\n{body}" if body else head

    wid = (
        str(gctx.extras.get("web_session_id") or gctx.extras.get("conversation_id") or "default").strip()[:64]
        or "default"
    )
    title = title_for_payload(safe)
    try:
        job = enqueue_host_job_from_validated_payload(
            db,
            uid.strip(),
            safe_pl=safe,
            title=title,
            web_session_id=wid,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("operator NL readme chain enqueue failed: %s", exc, exc_info=False)
        return None
    return (
        "### Queued for you\n\n"
        f"README, commit, and push are **queued** as one job (**#{job.id}**, {n} steps). "
        "Open **Jobs** and approve to run on the worker."
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
    pulse_text: str | None,
    live_steps: list[str],
) -> tuple[list[str], dict[str, Any], list[str]]:
    """Run gated test / commit / push / deploy / verify phases. Returns (sections, evidence, progress)."""
    from app.services.operator_pulse import pulse_requests_no_production_deploy

    ws = _workspace_for_phases(db, uid, ws_hint)
    if not ws or not _wants_phase_keywords(raw):
        return [], [], []

    cue = _strip_workspace_clause(raw)

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
    skip_deploy = pulse_requests_no_production_deploy(pulse_text)

    if re.search(r"(?i)\b(test|tests|pytest|npm test)\b", cue):
        live_steps.append("Running tests in the workspace…")
        prog.append("Running tests")
        tr = run_tests(ws)
        ev["tests"] = tr
        sections.append(_phase_result_markdown("Phase: test", tr))

    if (re.search(r"(?i)\bcommit\b", cue) and re.search(r"(?i)\bpush\b", cue)) or re.search(
        r"(?i)push\s+changes", cue
    ):
        live_steps.append("Committing with a semantic message and pushing to `origin`…")
        prog.append("Committing and pushing")
        cp = commit_and_push(ws, "operator: automated checkpoint")
        ev["commit_push"] = cp
        sections.append(_phase_result_markdown("Phase: commit + push", cp))

    if vercel_cue and re.search(r"\bdeploy\b", cue, re.I):
        if skip_deploy:
            live_steps.append("Checking PULSE.md — skipping production deploy per standing orders…")
            prog.append("Deploy skipped (PULSE.md)")
            ev["deploy_vercel"] = {
                "ok": True,
                "noop": True,
                "skipped_by_pulse": True,
                "message": "PULSE.md requests no production deploy; deploy phase not run.",
            }
            sections.append(
                "### Phase: deploy (Vercel)\n\n"
                "**Skipped:** `PULSE.md` standing orders ask not to deploy to production. "
                "Adjust the file or override intent if a deploy is truly required."
            )
        else:
            live_steps.append("Deploying to Vercel (production)…")
            prog.append("Deploying to Vercel (production)")
            dv = deploy_vercel(ws)
            ev["deploy_vercel"] = dv
            sections.append(_phase_result_markdown("Phase: deploy (Vercel)", dv))

    if railway_cue and re.search(r"\b(deploy|railway up)\b", cue, re.I):
        if skip_deploy:
            live_steps.append("Checking PULSE.md — skipping Railway deploy per standing orders…")
            prog.append("Railway deploy skipped (PULSE.md)")
            ev["deploy_railway"] = {
                "ok": True,
                "noop": True,
                "skipped_by_pulse": True,
                "message": "PULSE.md requests no production deploy; deploy phase not run.",
            }
            sections.append(
                "### Phase: deploy (Railway)\n\n"
                "**Skipped:** `PULSE.md` standing orders ask not to deploy. "
                "Adjust the file if a deploy is truly required."
            )
        else:
            live_steps.append("Deploying via Railway…")
            prog.append("Deploying via Railway")
            dr = deploy_railway(ws)
            ev["deploy_railway"] = dr
            sections.append(_phase_result_markdown("Phase: deploy (Railway)", dr))

    url = extract_production_url(raw)
    if url and re.search(r"\bverify\b", cue, re.I):
        live_steps.append("Watching deployment output and verifying production health (HTTP check)…")
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
    from app.services.provider_router import (
        apply_router_to_operator_hints,
        detect_primary_provider,
        extract_urls_from_text,
    )

    hints = apply_router_to_operator_hints(raw, hints)
    from app.services.intent_focus_filter import extract_focused_intent

    focused = extract_focused_intent(raw)
    if focused.get("ignore_railway"):
        hints["railway"] = False
        logger.info("operator_execution.focused_intent ignore_railway=true (Vercel-scoped turn)")
    _prov_det, _conf_det = detect_primary_provider(raw, extract_urls_from_text(raw))
    logger.info(
        "operator_execution.dynamic_provider provider=%s confidence=%.2f",
        _prov_det,
        _conf_det,
    )
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

    from app.services.operator_pulse import format_pulse_section, read_pulse_standing_orders

    pulse_enabled = bool(getattr(settings, "nexa_pulse_injection", True))
    # Fresh read every operator turn when injection is enabled (no cache).
    pulse = read_pulse_standing_orders(ws_resolved) if pulse_enabled else None

    sections: list[str] = []
    evidence: dict[str, Any] = {}
    progress: list[str] = []
    runner_ok = False
    primary_provider: str | None = None
    live: list[str] = []

    cwd = ws_path if ws_path else None

    if vercel_cue:
        live.append("Inspecting Vercel project and recent deployment activity…")
        primary_provider = primary_provider or "vercel"
        body_v, ev_v, prog_v, v_ok = run_vercel_operator_readonly(cwd=cwd)
        sections.append(body_v)
        evidence["vercel"] = ev_v
        progress.extend(prog_v)
        runner_ok = runner_ok or v_ok

    if gh_cue:
        live.append("Inspecting GitHub authentication and repository state…")
        primary_provider = primary_provider or "github"
        body_g, ev_g, prog_g, g_ok = run_github_operator_readonly(cwd=cwd)
        sections.append(body_g)
        if g_ok:
            q_readme = _try_enqueue_readme_push_chain_after_github(db, uid, raw, gctx)
            if q_readme:
                sections.append(q_readme)
        evidence["github"] = ev_g
        progress.extend(prog_g)
        runner_ok = runner_ok or g_ok

    if ws_path:
        live.append("Inspecting workspace and `git status`…")
        primary_provider = primary_provider or "local_dev"
        body_l, ev_l, prog_l, l_ok = run_git_status_at_path(ws_path)
        sections.append(body_l)
        evidence["local_dev"] = ev_l
        progress.extend(prog_l)
        runner_ok = runner_ok or l_ok
    elif hints["local_git"] and not vercel_cue and not gh_cue:
        live.append("Inspecting workspace and `git status`…")
        primary_provider = primary_provider or "local_dev"
        body_l, ev_l, prog_l, l_ok = run_local_git_status(db, uid)
        sections.append(body_l)
        evidence["local_dev"] = ev_l
        progress.extend(prog_l)
        runner_ok = runner_ok or l_ok

    if phase_only and not sections:
        live.append("Inspecting workspace and `git status`…")
        primary_provider = primary_provider or "local_dev"
        body_l, ev_l, prog_l, l_ok = run_local_git_status(db, uid)
        sections.append(body_l)
        evidence["local_dev"] = ev_l
        progress.extend(prog_l)
        runner_ok = runner_ok or l_ok

    if pulse:
        live.append("Reading `PULSE.md` standing orders…")

    ws_patch = ws_path or ws_resolved
    if ws_patch and "```diff" in raw.lower():
        from app.services.operator_execution_actions import apply_code_fix

        m = re.search(r"```diff\s*\n(.*?)```", raw, re.S | re.I)
        if m:
            live.append("Applying fix via unified diff patch…")
            progress.append("Applying embedded unified diff")
            ap = apply_code_fix(ws_patch, m.group(1).strip())
            evidence["patch"] = ap
            sections.append(_phase_result_markdown("Phase: fix (patch)", ap))
            runner_ok = runner_ok or bool(ap.get("ok"))

    phase_secs, phase_ev, phase_prog = _append_operator_phases(
        raw=raw,
        db=db,
        uid=uid,
        ws_hint=ws_path,
        vercel_cue=vercel_cue,
        railway_cue=railway_cue,
        pulse_text=pulse,
        live_steps=live,
    )
    if phase_secs:
        sections.extend(phase_secs)
        evidence["phases"] = phase_ev
        progress.extend(phase_prog)

    if not sections:
        return OperatorExecutionResult(handled=False, text="")

    merged = "\n\n---\n\n".join(sections)

    if pulse and not _precise_short_enabled():
        merged = merged + "\n\n---\n\n" + format_pulse_section(pulse)

    phases_ok = True
    if isinstance(evidence.get("phases"), dict) and evidence["phases"]:
        phases_ok = all(
            isinstance(v, dict) and v.get("ok") for v in evidence["phases"].values()
        )
    verified_loose = runner_ok and phases_ok

    strict_v = _compute_strict_operator_verified(evidence, runner_ok=verified_loose)

    merged = forbid_unverified_success_language(strict_verified=strict_v, body=merged)
    merged = _append_verified_mission_footer(merged, strict_verified=strict_v, evidence=evidence)

    if _precise_short_enabled():
        live_block = _format_live_progress_precise(primary_provider)
    else:
        live_block = _format_live_progress_steps(live)
    if live_block:
        merged = live_block + "\n\n---\n\n" + merged
    elif not any(x in merged for x in ("### Progress", "→ ")):
        if _precise_short_enabled():
            merged = _format_live_progress_precise(primary_provider) + "\n\n---\n\n" + merged
        else:
            merged = format_operator_progress(progress or ["Starting operator diagnostics"]) + "\n\n---\n\n" + merged

    needs_verify = False
    ph = evidence.get("phases")
    if isinstance(ph, dict):
        dv, dr = ph.get("deploy_vercel"), ph.get("deploy_railway")
        if isinstance(dv, dict) and dv.get("ok") and not dv.get("noop") and not _http_verify_strict_ok(
            ph.get("verify")
        ):
            needs_verify = True
        if isinstance(dr, dict) and dr.get("ok") and not dr.get("noop") and not _http_verify_strict_ok(
            ph.get("verify")
        ):
            needs_verify = True

    if strict_v:
        blocker = None
    elif needs_verify:
        blocker = "verification_required"
    elif verified_loose:
        blocker = "diagnostic_only"
    else:
        blocker = "diagnostic_only"

    logger.info(
        "operator_execution uid=%s providers=%s strict_verified=%s",
        uid,
        list(evidence.keys()),
        strict_v,
    )

    return OperatorExecutionResult(
        handled=True,
        text=merged,
        provider=primary_provider,
        ran=True,
        verified=strict_v,
        blocker=blocker,
        progress=progress,
        evidence=evidence,
    )


__all__ = ["OperatorExecutionResult", "try_operator_execution"]
