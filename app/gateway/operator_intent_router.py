# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Route NL provider intents → deploy context → provider actions (Phase 2 Step 5)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.deploy_context.context_execution import (
    execute_vercel_logs,
    execute_vercel_redeploy,
    execute_vercel_restart,
    execute_vercel_status,
)
from app.deploy_context.context_history import record_operator_provider_action
from app.deploy_context.context_resolution import build_deploy_context
from app.deploy_context.errors import OperatorDeployError, ProjectResolutionError
from app.gateway.provider_intents import parse_provider_operation_intent
from app.projects.project_registry_service import link_project_repo, scan_projects_registry
from app.providers.intelligence_service import scan_providers_inventory
from app.rendering.operator_responses import (
    render_egress_blocked,
    render_operator_deploy_error,
    render_privacy_blocked,
    render_provider_action_success,
)


def _privacy_allows_provider_nl(text: str) -> tuple[bool, str | None]:
    """Best-effort egress guard on operator text before provider CLI work."""
    try:
        from app.privacy.egress_guard import evaluate_egress
        from app.privacy.pii_detection import detect_pii

        s = get_settings()
        cats = [m.category for m in detect_pii(text or "")]
        ok, reason = evaluate_egress(s, "provider_cli", pii_categories=cats)
        if not ok:
            return False, reason
    except Exception:
        return True, None
    return True, None


def _append_resolution_history(
    project_id: str,
    intent: str,
    repo_path: str | None,
    provider: str,
    success: bool,
) -> None:
    from app.runtime.runtime_state import (
        ensure_operator_context_schema,
        load_runtime_state,
        save_runtime_state,
        utc_now_iso,
    )

    st = load_runtime_state()
    ensure_operator_context_schema(st)
    hist = st.setdefault("project_resolution_history", [])
    if isinstance(hist, list):
        hist.append(
            {
                "ts": utc_now_iso(),
                "action": intent,
                "source": "gateway_nl",
                "project_id": project_id,
                "repo_path": repo_path,
                "provider": provider,
                "success": success,
            }
        )
        st["project_resolution_history"] = hist[-200:]
        save_runtime_state(st)


def _record_nl_action(
    *,
    intent: str,
    project_id: str | None,
    provider: str,
    success: bool,
    summary: str,
    extra: dict[str, Any] | None = None,
) -> None:
    row: dict[str, Any] = {
        "source": "gateway_nl",
        "intent": intent,
        "provider": provider,
        "project_id": project_id,
        "success": success,
        "summary": summary[:2000],
    }
    if extra:
        row.update(extra)
    record_operator_provider_action(row)


def _gateway_reply(
    body: str,
    *,
    raw: str,
    intent: str,
    success: bool = True,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from app.services.gateway.runtime import gateway_finalize_chat_reply

    out: dict[str, Any] = {
        "mode": "chat",
        "text": gateway_finalize_chat_reply(body.strip(), source="provider_operations_nl", user_text=raw),
        "intent": intent,
        "provider_operation": True,
    }
    if extra:
        out.update(extra)
    out["success"] = success
    return out


def execute_provider_nl_intent(parsed: dict[str, Any]) -> dict[str, Any]:
    """Run a parsed provider intent; returns gateway payload dict."""
    raw = str(parsed.get("raw_text") or "")
    intent = str(parsed.get("intent") or "")
    provider = str(parsed.get("provider") or "vercel")
    environment = str(parsed.get("environment") or "production")

    allowed, reason = _privacy_allows_provider_nl(raw)
    if not allowed:
        mode = (get_settings().aethos_privacy_mode or "").strip().lower()
        body = render_egress_blocked(reason) if mode == "block" else render_privacy_blocked(reason)
        _record_nl_action(
            intent=intent,
            project_id=parsed.get("project_id"),
            provider=provider,
            success=False,
            summary="privacy_blocked",
        )
        return _gateway_reply(body, raw=raw, intent="privacy_blocked", success=False)

    if intent == "provider_scan_providers":
        inv = scan_providers_inventory(persist=True)
        n = len((inv.get("providers") or {}))
        _record_nl_action(intent=intent, project_id=None, provider=provider, success=True, summary=f"scanned {n} providers")
        return _gateway_reply(
            f"**Provider scan complete.**\n\nTracked **{n}** provider(s).\n\n"
            "Use `aethos providers list` for details.",
            raw=raw,
            intent=intent,
        )

    if intent == "provider_scan_projects":
        reg = scan_projects_registry(persist=True)
        n = len((reg.get("projects") or {}))
        _record_nl_action(intent=intent, project_id=None, provider=provider, success=True, summary=f"scanned {n} projects")
        return _gateway_reply(
            f"**Project scan complete.**\n\nFound **{n}** local project(s).\n\n"
            "Use `aethos projects list` or link a repo with `aethos projects link <slug> <path>`.",
            raw=raw,
            intent=intent,
        )

    if intent == "provider_link_project":
        phrase = str(parsed.get("project_phrase") or "")
        repo_path = str(parsed.get("repo_path") or "")
        from app.deploy_context.nl_resolution import extract_project_slug_from_phrase
        from app.projects.vercel_link import slugify_project_id

        pid, _ = extract_project_slug_from_phrase(phrase)
        slug = pid or slugify_project_id(phrase)
        row = link_project_repo(slug, repo_path, persist=True)
        if not row:
            return _gateway_reply("Could not link project — check the slug and path.", raw=raw, intent=intent, success=False)
        _record_nl_action(intent=intent, project_id=slug, provider=provider, success=True, summary="linked")
        return _gateway_reply(
            f"Linked **{slug}** → `{repo_path}`",
            raw=raw,
            intent=intent,
        )

    project_id = parsed.get("project_id")
    if not project_id:
        cands = parsed.get("candidates") or []
        phrase = parsed.get("project_phrase") or "that project"
        exc = ProjectResolutionError(
            f"I could not safely determine which project you meant for {phrase!r}.",
            suggestions=["aethos projects scan", "aethos projects link <slug> <path>"],
            details={"candidates": cands},
        )
        _record_nl_action(
            intent=intent,
            project_id=None,
            provider=provider,
            success=False,
            summary="ProjectResolutionError",
        )
        return _gateway_reply(
            render_operator_deploy_error(exc),
            raw=raw,
            intent="project_not_found",
            success=False,
        )

    pid = str(project_id)
    try:
        if intent in ("provider_restart",):
            result = execute_vercel_restart(pid, environment=environment)
        elif intent in ("provider_redeploy", "provider_deploy"):
            result = execute_vercel_redeploy(pid, environment=environment)
        elif intent == "provider_status":
            result = execute_vercel_status(pid, environment=environment)
        elif intent == "provider_logs":
            result = execute_vercel_logs(pid, environment=environment, limit=80)
        elif intent == "provider_inspect":
            ctx = build_deploy_context(pid, provider=provider, environment=environment)
            from app.providers.actions import vercel_actions

            result = vercel_actions.inspect_project_cli(ctx)
        else:
            return _gateway_reply(f"Unsupported provider intent: {intent}", raw=raw, intent=intent, success=False)
    except OperatorDeployError as exc:
        _record_nl_action(
            intent=intent,
            project_id=pid,
            provider=provider,
            success=False,
            summary=exc.__class__.__name__,
        )
        return _gateway_reply(
            render_operator_deploy_error(exc),
            raw=raw,
            intent=intent.replace("provider_", "") + "_failed",
            success=False,
        )

    ok = bool(result.get("success"))
    ctx_path: str | None = None
    try:
        ctx = build_deploy_context(pid, provider=provider, environment=environment)
        ctx_path = str(ctx.get("repo_path") or "")
    except OperatorDeployError:
        pass

    _append_resolution_history(pid, intent, ctx_path, provider, ok)

    body = render_provider_action_success(
        intent=intent,
        project_id=pid,
        provider=provider,
        repo_path=ctx_path,
        result=result,
    )
    _record_nl_action(
        intent=intent,
        project_id=pid,
        provider=provider,
        success=ok,
        summary=str(result.get("summary") or result.get("action") or intent),
        extra={"deployment_id": result.get("deployment_id"), "url": result.get("url")},
    )
    return _gateway_reply(
        body,
        raw=raw,
        intent=intent if ok else intent.replace("provider_", "") + "_failed",
        success=ok,
        extra={"provider_result": result},
    )


def try_operator_provider_nl_turn(
    *,
    user_id: str,
    raw_message: str,
    db: Session | None = None,
) -> dict[str, Any] | None:
    """
    Parse and execute provider NL intents.

    ``db`` is accepted for gateway signature compatibility; persistence uses runtime state.
    """
    _ = db
    uid = (user_id or "").strip()
    raw = (raw_message or "").strip()
    if not uid or not raw:
        return None

    parsed = parse_provider_operation_intent(raw)
    if not parsed:
        return None

    try:
        return execute_provider_nl_intent(parsed)
    except OperatorDeployError as exc:
        intent = str(parsed.get("intent") or "provider_error")
        _record_nl_action(
            intent=intent,
            project_id=parsed.get("project_id"),
            provider=str(parsed.get("provider") or "vercel"),
            success=False,
            summary=exc.__class__.__name__,
        )
        return _gateway_reply(
            render_operator_deploy_error(exc),
            raw=raw,
            intent=intent.replace("provider_", "") + "_failed",
            success=False,
        )


__all__ = ["execute_provider_nl_intent", "try_operator_provider_nl_turn"]
