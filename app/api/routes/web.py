"""Browser Web UI — Phase 1: sessions, chat, jobs, keys, system status. Reuses core services."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.models.access_permission import AccessPermission
from app.models.conversation_context import ConversationContext
from app.repositories.telegram_repo import TelegramRepository
from app.schemas.agent_job import AgentJobApprovalRequest, AgentJobRead
from app.schemas.memory import (
    AgentMemoryState,
    MemoryForgetRequest,
    MemoryForgetResult,
    MemoryNoteDeleteRequest,
    MemoryNoteRead,
    MemoryNoteUpdateRequest,
    MemoryRememberRequest,
    PreferencesRead,
    PreferencesUpdate,
    SoulUpdateRequest,
)
from app.schemas.web_ui import (
    DecisionSummaryOut,
    FlowSummaryItemOut,
    SystemEventItemOut,
    UsageSummaryOut,
    WebAccessPermissionGrantIn,
    WebAccessPermissionOut,
    WebActiveWorkspaceProjectResponse,
    WebByokKeyIn,
    WebByokKeyRow,
    WebChatMessageIn,
    WebChatMessageOut,
    WebDocumentGenerateIn,
    WebDocumentGenerateOut,
    WebDocumentItemOut,
    WebHostExecutorPanelOut,
    WebIndicatorItem,
    WebMessageItem,
    WebNexaWorkspaceProjectCreateIn,
    WebNexaWorkspaceProjectOut,
    WebReleaseLatestOut,
    WebReleaseNotesOut,
    WebSessionActiveProjectIn,
    WebSessionCreatedOut,
    WebSessionCreateIn,
    WebSessionOut,
    WebSystemStatusOut,
    WebWorkContextOut,
    WebWorkspaceRootCreateIn,
    WebWorkspaceRootOut,
)
from app.services import release_updates, user_api_keys
from app.services.access_permissions import (
    GRANT_MODE_PERSISTENT,
)
from app.services.access_permissions import (
    grant_permission as ap_grant_permission,
)
from app.services.access_permissions import (
    list_permissions as ap_list_permissions,
)
from app.services.access_permissions import (
    revoke_permission as ap_revoke_permission,
)
from app.services.agent_job_service import AgentJobService
from app.services.app_user_id_parse import parse_telegram_id_from_app_user_id
from app.services.channel_gateway.router import handle_incoming_channel_message
from app.services.conversation_context_service import (
    create_new_web_conversation_context,
    delete_or_clear_web_session,
    get_conversation_context_by_session,
    get_or_create_context,
    list_conversation_contexts_for_user,
)
from app.services.document_generation import (
    DocumentGenerationError,
    generate_document,
    get_document_path_for_owner,
    list_document_artifacts_for_user,
)
from app.services.host_executor_visibility import host_executor_public
from app.services.llm_usage_recorder import (
    build_llm_usage_summary,
    format_usage_subline,
    get_recent_llm_usage,
    get_session_usage_summary,
    get_usage_by_day,
)
from app.services.memory_service import MemoryService
from app.services.nexa_doctor import build_nexa_doctor_text
from app.services.nexa_workspace_project_registry import (
    add_workspace_project as nxp_add,
)
from app.services.nexa_workspace_project_registry import (
    list_workspace_projects as nxp_list,
)
from app.services.nexa_workspace_project_registry import (
    remove_workspace_project as nxp_remove,
)
from app.services.nexa_workspace_project_registry import (
    set_active_workspace_project as nxp_set_active,
)
from app.services.user_api_keys import (
    delete_user_api_key,
    list_user_providers,
    normalize_provider,
    set_user_api_key,
)
from app.services.user_capabilities import (
    get_telegram_role_for_app_user,
    is_owner_role,
    require_personal_workspace_mutation_allowed,
)
from app.services.work_context import build_work_context
from app.services.worker_heartbeat import read_heartbeat
from app.services.workspace_registry import add_root as wr_add_root
from app.services.workspace_registry import list_roots as wr_list_roots
from app.services.workspace_registry import revoke_root as wr_revoke_root

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/web", tags=["web"])
job_service = AgentJobService()
_memory_service = MemoryService()

_DEFAULT_WEB_SESSION = "default"


def _web_access_perm_out(row: AccessPermission) -> WebAccessPermissionOut:
    md = dict(row.metadata_json or {})
    gm = (md.get("grant_mode") or GRANT_MODE_PERSISTENT) or GRANT_MODE_PERSISTENT
    return WebAccessPermissionOut(
        id=row.id,
        scope=row.scope,
        target=row.target,
        risk_level=row.risk_level,
        status=row.status,
        expires_at=row.expires_at,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        reason=row.reason,
        grant_mode=str(gm),
    )


def _norm_web_session_id(raw: str | None) -> str:
    s = (raw or _DEFAULT_WEB_SESSION).strip()[:64] or _DEFAULT_WEB_SESSION
    return s


def _preview_for_session_row(cctx: ConversationContext) -> str | None:
    try:
        recent = json.loads(cctx.recent_messages_json or "[]")
    except (json.JSONDecodeError, TypeError, ValueError):
        recent = []
    if not isinstance(recent, list):
        return None
    for m in recent:
        if not isinstance(m, dict):
            continue
        if str(m.get("role") or "") != "user":
            continue
        t = str(m.get("text", m.get("content", ""))).strip()
        if t:
            return t[:200] if len(t) <= 200 else t[:197] + "…"
    at = (cctx.active_topic or "").strip()
    if at:
        return at[:200] if len(at) <= 200 else at[:197] + "…"
    return None


def _conversation_context_to_session_out(cctx: ConversationContext) -> WebSessionOut:
    try:
        recent = json.loads(cctx.recent_messages_json or "[]")
    except (json.JSONDecodeError, TypeError, ValueError):
        recent = []
    n = len(recent) if isinstance(recent, list) else 0
    sid = (cctx.session_id or _DEFAULT_WEB_SESSION).strip() or _DEFAULT_WEB_SESSION
    title0 = (cctx.web_chat_title or "").strip() or (
        "Main session" if sid == _DEFAULT_WEB_SESSION else "Chat"
    )
    return WebSessionOut(
        id=sid,
        title=title0,
        summary=(cctx.summary or None)[:500] if cctx.summary else None,
        active_topic=(cctx.active_topic or None),
        last_agent=(cctx.active_agent or cctx.last_agent_key or None),
        last_intent=(cctx.last_intent or None),
        updated_at=getattr(cctx, "updated_at", None),
        message_count=n,
        preview=_preview_for_session_row(cctx),
    )


def _require_telegram_id(db: Session, app_user_id: str) -> int:
    tid = parse_telegram_id_from_app_user_id(app_user_id)
    if tid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="BYOK requires X-User-Id in the form tg_<telegram_user_id> (Telegram-linked account).",
        )
    return tid


@router.get("/me")
def web_me(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    link = TelegramRepository().get_by_app_user(db, app_user_id)
    o = is_owner_role(get_telegram_role_for_app_user(db, app_user_id))
    return {
        "app_user_id": app_user_id,
        "telegram_user_id": link.telegram_user_id if link else None,
        "username": (link.username or None) if link else None,
        "is_owner": o,
        "show_cost_details_default": o,
    }


@router.get("/work-context", response_model=WebWorkContextOut)
def get_work_context(
    session_id: str | None = Query(
        default=None,
        max_length=64,
        description="Web chat session id (ConversationContext.session_id); default = main session",
    ),
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> WebWorkContextOut:
    wid = _norm_web_session_id(session_id)
    if wid == _DEFAULT_WEB_SESSION:
        cctx = get_or_create_context(db, app_user_id, web_session_id=_DEFAULT_WEB_SESSION)
    else:
        cctx = get_conversation_context_by_session(db, app_user_id, wid)
        if cctx is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unknown session",
            )
    raw = build_work_context(db, cctx, app_user_id)
    return WebWorkContextOut(
        flow=FlowSummaryItemOut(**raw["flow"]),
        lines=list(raw.get("lines") or []),
        recent_artifacts=list(raw.get("recent_artifacts") or []),
    )


@router.get("/sessions", response_model=list[WebSessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> list[WebSessionOut]:
    get_or_create_context(db, app_user_id, web_session_id=_DEFAULT_WEB_SESSION)
    rows = list_conversation_contexts_for_user(db, app_user_id)
    # Always surface the default session even when the user has >50 newer chats.
    sids = {(c.session_id or _DEFAULT_WEB_SESSION).strip() or _DEFAULT_WEB_SESSION for c in rows}
    if _DEFAULT_WEB_SESSION not in sids:
        d = get_conversation_context_by_session(db, app_user_id, _DEFAULT_WEB_SESSION)
        if d is not None:
            rows = [d, *rows]
    return [_conversation_context_to_session_out(c) for c in rows]


@router.post("/sessions", response_model=WebSessionCreatedOut)
def create_web_session(
    body: WebSessionCreateIn,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> WebSessionCreatedOut:
    get_or_create_context(db, app_user_id, web_session_id=_DEFAULT_WEB_SESSION)
    row = create_new_web_conversation_context(db, app_user_id, title=body.title)
    t = (row.web_chat_title or "New chat").strip() or "New chat"
    return WebSessionCreatedOut(id=row.session_id, title=t)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_web_session(
    session_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> Response:
    wid = _norm_web_session_id(session_id)
    try:
        delete_or_clear_web_session(db, app_user_id, wid)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown session",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sessions/{session_id}/messages", response_model=list[WebMessageItem])
def get_session_messages(
    session_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> list[WebMessageItem]:
    wid = (session_id or "").strip()[:64] or _DEFAULT_WEB_SESSION
    if wid == _DEFAULT_WEB_SESSION:
        cctx = get_or_create_context(db, app_user_id, web_session_id=_DEFAULT_WEB_SESSION)
    else:
        cctx = get_conversation_context_by_session(db, app_user_id, wid)
        if cctx is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown session")
    try:
        recent = json.loads(cctx.recent_messages_json or "[]")
    except json.JSONDecodeError:
        recent = []
    if not isinstance(recent, list):
        return []
    out: list[WebMessageItem] = []
    for m in recent:
        if m is None:
            continue
        if not isinstance(m, dict):
            continue
        body = m.get("text", m.get("content", ""))
        out.append(
            WebMessageItem(
                role=str(m.get("role", "user"))[:12],
                content=str(body)[:8000],
            )
        )
    return out


@router.post("/chat", response_model=WebChatMessageOut)
def post_chat(
    body: WebChatMessageIn,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> WebChatMessageOut:
    try:
        from app.services.observability import get_observability

        get_observability().record_metric("api.web.chat.requests", 1.0, "count")
    except Exception:
        pass
    link = TelegramRepository().get_by_app_user(db, app_user_id)
    un = (link.username or None) if link else None
    w_sid = _norm_web_session_id(body.session_id)
    env = handle_incoming_channel_message(
        db,
        normalized_message={
            "channel": "web",
            "channel_user_id": app_user_id,
            "user_id": app_user_id,
            "message": body.message,
            "attachments": [],
            "metadata": {
                "web_session_id": w_sid,
                "username": un,
            },
        },
    )
    related: list[AgentJobRead] = []
    for jid in env["related_job_ids"]:
        try:
            related.append(job_service.get_job(db, app_user_id, int(jid)))
        except HTTPException:
            pass
    u_sum: UsageSummaryOut | None = None
    us_raw = env.get("usage_summary")
    if us_raw:
        us = dict(us_raw)
        u_sum = UsageSummaryOut(
            used_llm=bool(us.get("used_llm", False)),
            input_tokens=int(us.get("input_tokens", 0) or 0),
            output_tokens=int(us.get("output_tokens", 0) or 0),
            total_tokens=int(us.get("total_tokens", 0) or 0),
            estimated_cost_usd=us.get("estimated_cost_usd") if us.get("estimated_cost_usd") is not None else None,
            provider=(str(us.get("provider")) if us.get("provider") is not None else None),
            model=(str(us.get("model")) if us.get("model") is not None else None),
            used_user_key=bool(us.get("used_user_key", False)),
            subline=format_usage_subline(us_raw),
        )
    dsum: DecisionSummaryOut | None = None
    if env.get("decision_summary"):
        d = env["decision_summary"]
        dsum = DecisionSummaryOut(
            agent=str(d.get("agent") or "aethos")[:64],
            action=str(d.get("action") or "chat_response")[:64],
            tool=(str(d["tool"])[:64] if d.get("tool") is not None else None),
            reason=(str(d.get("reason") or ""))[:2000],
            risk=str(d.get("risk") or "low")[:32],
            approval_required=bool(d.get("approval_required", False)),
            intent=(str(d["intent"])[:64] if d.get("intent") is not None else None),
        )
    se_items = [
        SystemEventItemOut(
            kind=str((x or {}).get("kind") or "")[:64],
            text=str((x or {}).get("text") or "")[:1200],
        )
        for x in (env.get("system_events") or [])
        if isinstance(x, dict)
    ]
    return WebChatMessageOut(
        reply=env["message"],
        intent=env.get("intent"),
        agent_key=env.get("agent_key"),
        related_jobs=related,
        response_kind=env.get("response_kind"),
        permission_required=env.get("permission_required"),
        sources=env.get("sources") or [],
        web_tool_line=env.get("web_tool_line"),
        usage_summary=u_sum,
        request_id=env.get("request_id"),
        decision_summary=dsum,
        system_events=se_items,
    )


@router.get("/jobs", response_model=list[AgentJobRead])
def list_web_jobs(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
    limit: int = 200,
) -> list:
    return job_service.list_jobs(db, app_user_id, limit=min(limit, 500))


@router.get("/jobs/{job_id}", response_model=AgentJobRead)
def get_web_job(
    job_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> Any:
    return job_service.get_job(db, app_user_id, job_id)


@router.post("/jobs/{job_id}/decision", response_model=AgentJobRead)
def decide_web_job(
    job_id: int,
    payload: AgentJobApprovalRequest,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> Any:
    return job_service.decide(db, app_user_id, job_id, payload.decision)


@router.post("/jobs/{job_id}/cancel", response_model=AgentJobRead)
def cancel_web_job(
    job_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> Any:
    """Phase 70 — web proxy for ``AgentJobService.cancel`` so the Mission Control
    Approvals panel can dismiss a pending job from the same auth surface as the
    decision endpoint."""
    return job_service.cancel(db, app_user_id, job_id)


@router.get("/keys", response_model=list[WebByokKeyRow])
def list_keys(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> list[WebByokKeyRow]:
    tid = _require_telegram_id(db, app_user_id)
    return [
        WebByokKeyRow(
            provider=m.provider,
            has_key=m.has_key,
            last4=(m.last4 or "").replace("\u2022", "*"),
        )
        for m in list_user_providers(db, tid)
    ]


@router.post("/keys", response_model=WebByokKeyRow)
def set_key(
    body: WebByokKeyIn,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> WebByokKeyRow:
    tid = _require_telegram_id(db, app_user_id)
    p = normalize_provider(body.provider)
    if not p:
        raise HTTPException(status_code=400, detail="Invalid provider; use openai or anthropic.")
    ok, msg = set_user_api_key(db, tid, p, body.key)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    for m in list_user_providers(db, tid):
        if m.provider == p:
            return WebByokKeyRow(provider=m.provider, has_key=m.has_key, last4=m.last4 or "")
    return WebByokKeyRow(provider=p, has_key=True, last4="****")


@router.delete("/keys/{provider}")
def remove_key(
    provider: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, str]:
    tid = _require_telegram_id(db, app_user_id)
    p = normalize_provider(provider) or (provider or "").strip().lower()
    if p not in user_api_keys.PROVIDERS:
        raise HTTPException(status_code=400, detail="Invalid provider")
    if not delete_user_api_key(db, tid, p):
        raise HTTPException(status_code=404, detail="Key not set")
    return {"status": "ok"}


@router.get("/memory/state", response_model=AgentMemoryState)
def web_memory_state(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> AgentMemoryState:
    return _memory_service.get_state(db, app_user_id)


@router.get("/memory", response_model=PreferencesRead)
def web_memory_preferences(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> PreferencesRead:
    return _memory_service.get_preferences(db, app_user_id)


@router.put("/memory/preferences", response_model=PreferencesRead)
def web_memory_update_preferences(
    payload: PreferencesUpdate,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> PreferencesRead:
    return _memory_service.update_preferences(db, app_user_id, payload)


@router.post("/memory/remember", response_model=MemoryNoteRead)
def web_memory_remember(
    payload: MemoryRememberRequest,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> MemoryNoteRead:
    return _memory_service.remember_note(
        db, app_user_id, payload.content, category=payload.category, source="api"
    )


@router.patch("/memory/notes", response_model=MemoryNoteRead)
def web_memory_update_note(
    payload: MemoryNoteUpdateRequest,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> MemoryNoteRead:
    return _memory_service.update_note(
        db, app_user_id, payload.key, payload.content, category=payload.category, source="api"
    )


@router.post("/memory/notes/delete")
def web_memory_delete_note(
    payload: MemoryNoteDeleteRequest,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, bool]:
    return {"deleted": _memory_service.delete_note(db, app_user_id, payload.key)}


@router.post("/memory/forget", response_model=MemoryForgetResult)
def web_memory_forget(
    payload: MemoryForgetRequest,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> MemoryForgetResult:
    return _memory_service.forget(db, app_user_id, payload.query)


@router.put("/memory/soul", response_model=str)
def web_memory_update_soul(
    payload: SoulUpdateRequest,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> str:
    return _memory_service.update_soul_markdown(db, app_user_id, payload.content, source="api")


@router.get("/release-notes", response_model=WebReleaseNotesOut)
def web_release_notes() -> WebReleaseNotesOut:
    """
    Public — no auth. User-facing highlights from root CHANGELOG.md; safe if file is missing.
    """
    data = release_updates.get_latest_release_update()
    rid = (data.get("release_id") or "").strip() or "unknown"
    d = (data.get("date_label") or rid).strip()
    return WebReleaseNotesOut(
        release_id=rid,
        date=d,
        title=(data.get("headline") or "AethOS")[:200],
        items=[str(x)[:500] for x in (data.get("bullets") or []) if str(x).strip()][:20],
        full_text=(data.get("raw_section") or "")[:50_000],
    )


@router.get("/release/latest", response_model=WebReleaseLatestOut)
def web_release_latest(
    _app_user_id: str = Depends(get_valid_web_user_id),
) -> WebReleaseLatestOut:
    """Latest release id + short bullets + section body; requires normal web auth headers."""
    payload = release_updates.get_release_latest_for_web()
    rid = str(payload.get("release_id") or "").strip()
    raw_items = payload.get("items") or []
    items = [str(x)[:500] for x in raw_items if str(x).strip()][:20]
    ft = str(payload.get("full_text") or "")[:50_000]
    return WebReleaseLatestOut(release_id=rid, items=items, full_text=ft)


@router.get("/system/doctor")
def system_doctor(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, str]:
    """
    Best-effort doctor text. Never raises HTTP 500: failures become diagnostic text
    in the `text` field (browser always gets HTTP 200 + JSON when auth succeeds).
    """
    tid = parse_telegram_id_from_app_user_id(app_user_id)
    try:
        return {"text": build_nexa_doctor_text(db, app_user_id, telegram_user_id=tid)}
    except Exception as exc:  # noqa: BLE001
        logger.exception("web system doctor failed: user=%r", app_user_id)
        body = (
            f"AethOS Doctor (partial: build failed)\n\n"
            f"Error: {type(exc).__name__}: {exc!s}\n"
            f"Check API logs for a full traceback. /api/v1/web/system/status may still be OK."
        )[:20_000]
        return {"text": body}


def _web_usage_is_owner(db: Session, app_user_id: str) -> bool:
    return is_owner_role(get_telegram_role_for_app_user(db, app_user_id))


@router.get("/usage/summary")
def web_usage_summary(
    period: str = "today",
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    return build_llm_usage_summary(
        period, db, app_user_id, is_owner=_web_usage_is_owner(db, app_user_id)
    )


@router.get("/usage/recent")
def web_usage_recent(
    limit: int = 50,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    o = _web_usage_is_owner(db, app_user_id)
    return {
        "items": get_recent_llm_usage(
            db, min(limit, 200), app_user_id, is_owner=o
        ),
    }


@router.get("/usage/daily")
def web_usage_daily(
    days: int = 14,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    o = _web_usage_is_owner(db, app_user_id)
    return {
        "days": get_usage_by_day(
            min(max(days, 1), 90), db, app_user_id, is_owner=o
        )
    }


@router.get("/usage/session/{session_id}")
def web_usage_session(
    session_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    o = _web_usage_is_owner(db, app_user_id)
    return get_session_usage_summary(db, session_id, app_user_id, is_owner=o)


@router.get("/system/status", response_model=WebSystemStatusOut)
def system_status_compact(
    db: Session = Depends(get_db),
    _app_user_id: str = Depends(get_valid_web_user_id),
) -> WebSystemStatusOut:
    """Green / yellow / red style indicators; expand doctor text from /system/doctor when needed."""
    s = get_settings()
    out: list[WebIndicatorItem] = [
        WebIndicatorItem(
            id="api",
            label="API",
            level="ok",
            detail=(s.app_name or "aethos")[:64],
        )
    ]
    try:
        db.execute(text("SELECT 1"))
        out.append(WebIndicatorItem(id="database", label="Database", level="ok", detail="reachable"))
    except Exception as e:  # noqa: BLE001
        out.append(
            WebIndicatorItem(
                id="database",
                label="Database",
                level="error",
                detail=str(e)[:160],
            )
        )
    hb = read_heartbeat() or {}
    hst = (hb.get("status") or "").lower()
    if hst in ("alive", "ok", "working"):
        out.append(
            WebIndicatorItem(
                id="executor",
                label="Host worker",
                level="ok",
                detail=(hb.get("current_stage") or "heartbeat")[:200],
            )
        )
    elif bool(hb):
        out.append(
            WebIndicatorItem(
                id="executor",
                label="Host worker",
                level="warning",
                detail=str((hb.get("status") or "stale")[:200]),
            )
        )
    else:
        out.append(
            WebIndicatorItem(
                id="executor",
                label="Host worker",
                level="warning",
                detail="No heartbeat in .runtime/ — run the dev executor on the host to see status.",
            )
        )
    out.append(
        WebIndicatorItem(
            id="public_web",
            label="Public web",
            level="ok" if s.nexa_web_access_enabled else "warning",
            detail="enabled" if s.nexa_web_access_enabled else "disabled",
        )
    )
    out.append(
        WebIndicatorItem(
            id="browser_preview",
            label="Browser preview",
            level="ok" if s.nexa_browser_preview_enabled else "warning",
            detail="enabled" if s.nexa_browser_preview_enabled else "disabled (owner, optional)",
        )
    )
    pen = bool(s.nexa_web_search_enabled)
    prov = (s.nexa_web_search_provider or "none").lower().strip() or "none"
    has_key = bool((s.nexa_web_search_api_key or "").strip())
    if not pen:
        s_detail = "disabled"
        s_level = "warning"
    elif has_key and prov in ("brave", "tavily", "serpapi"):
        s_detail = f"enabled: {prov}"
        s_level = "ok"
    else:
        s_detail = "configured incorrectly (set provider and API key; see doctor)"
        s_level = "warning"
    out.append(
        WebIndicatorItem(
            id="web_search",
            label="Search",
            level=s_level,
            detail=s_detail,
        )
    )
    he = WebHostExecutorPanelOut(**host_executor_public())
    return WebSystemStatusOut(indicators=out, host_executor=he)


def _media_type_for_format(fmt: str) -> str:
    f = (fmt or "md").lower()
    if f == "pdf":
        return "application/pdf"
    if f == "docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if f == "txt":
        return "text/plain; charset=utf-8"
    return "text/markdown; charset=utf-8"


@router.post("/documents/generate", response_model=WebDocumentGenerateOut)
def web_document_generate(
    body: WebDocumentGenerateIn,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> WebDocumentGenerateOut:
    try:
        art = generate_document(
            db,
            title=body.title,
            body_markdown=body.body_markdown,
            format=body.format,
            user_id=app_user_id,
            source_type=body.source_type,
            source_ref=body.source_ref,
            allow_sensitive=body.allow_sensitive,
        )
    except DocumentGenerationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e) or e.code,
        ) from e
    return WebDocumentGenerateOut(
        id=art.id,
        title=art.title,
        format=art.format,
        download_url=art.download_url or f"/web/documents/{art.id}/download",
        created_at=art.created_at,
        metadata=art.metadata,
    )


@router.get("/documents", response_model=list[WebDocumentItemOut])
def web_document_list(
    limit: int = 30,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> list[WebDocumentItemOut]:
    items = list_document_artifacts_for_user(db, app_user_id, limit=min(max(limit, 1), 100))
    return [
        WebDocumentItemOut(
            id=a.id,
            title=a.title,
            format=a.format,
            file_path=a.file_path,
            source_type=a.source_type,
            source_ref=a.source_ref,
            created_at=a.created_at,
            download_url=a.download_url or f"/web/documents/{a.id}/download",
            metadata=a.metadata,
        )
        for a in items
    ]


@router.get("/documents/{doc_id}/download")
def web_document_download(
    doc_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> FileResponse:
    from app.models.document_artifact import DocumentArtifactModel

    row = db.get(DocumentArtifactModel, doc_id)
    if not row or row.owner_user_id != app_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    p = get_document_path_for_owner(db, doc_id, app_user_id)
    if p is None or not p.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing")
    stem = Path(row.file_path).name
    return FileResponse(
        path=p,
        filename=stem,
        media_type=_media_type_for_format(row.format),
    )


@router.get("/access/permissions", response_model=list[WebAccessPermissionOut])
def web_list_access_permissions(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> list[WebAccessPermissionOut]:
    rows = ap_list_permissions(db, app_user_id, limit=80)
    return [_web_access_perm_out(r) for r in rows]


@router.post("/access/permissions/{permission_id}/grant", response_model=WebAccessPermissionOut)
def web_grant_access_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
    body: WebAccessPermissionGrantIn | None = None,
) -> WebAccessPermissionOut:
    bm = body or WebAccessPermissionGrantIn()
    row = ap_grant_permission(
        db,
        app_user_id,
        permission_id,
        granted_by_user_id=app_user_id,
        grant_mode=bm.grant_mode,
        grant_session_hours=bm.grant_session_hours,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found or not pending",
        )
    return _web_access_perm_out(row)


@router.post("/access/permissions/{permission_id}/revoke", response_model=WebAccessPermissionOut)
def web_revoke_access_permission_route(
    permission_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> WebAccessPermissionOut:
    row = ap_revoke_permission(db, app_user_id, permission_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found or not revocable",
        )
    return _web_access_perm_out(row)


@router.get("/workspace/roots", response_model=list[WebWorkspaceRootOut])
def web_list_workspace_roots(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> list[WebWorkspaceRootOut]:
    rows = wr_list_roots(db, app_user_id, active_only=True)
    return [
        WebWorkspaceRootOut(
            id=r.id,
            path_normalized=r.path_normalized,
            label=r.label,
            is_active=r.is_active,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/workspace/roots", response_model=WebWorkspaceRootOut)
def web_add_workspace_root(
    body: WebWorkspaceRootCreateIn,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> WebWorkspaceRootOut:
    require_personal_workspace_mutation_allowed(db, app_user_id)
    try:
        r = wr_add_root(db, app_user_id, body.path, label=body.label)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return WebWorkspaceRootOut(
        id=r.id,
        path_normalized=r.path_normalized,
        label=r.label,
        is_active=r.is_active,
        created_at=r.created_at,
    )


def _nxp_out(row: Any) -> WebNexaWorkspaceProjectOut:
    return WebNexaWorkspaceProjectOut(
        id=row.id,
        name=row.name,
        path_normalized=row.path_normalized,
        description=row.description,
        created_at=row.created_at,
    )


@router.get("/workspace/nexa-projects", response_model=list[WebNexaWorkspaceProjectOut])
def web_list_nexa_workspace_projects(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> list[WebNexaWorkspaceProjectOut]:
    rows = nxp_list(db, app_user_id, limit=80)
    return [_nxp_out(r) for r in rows]


@router.post("/workspace/nexa-projects", response_model=WebNexaWorkspaceProjectOut)
def web_create_nexa_workspace_project(
    body: WebNexaWorkspaceProjectCreateIn,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> WebNexaWorkspaceProjectOut:
    require_personal_workspace_mutation_allowed(db, app_user_id)
    try:
        r = nxp_add(
            db,
            app_user_id,
            body.path,
            body.name,
            description=body.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return _nxp_out(r)


@router.delete("/workspace/nexa-projects/{project_id}", response_model=WebNexaWorkspaceProjectOut)
def web_delete_nexa_workspace_project(
    project_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> WebNexaWorkspaceProjectOut:
    require_personal_workspace_mutation_allowed(db, app_user_id)
    row = nxp_remove(db, app_user_id, project_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return _nxp_out(row)


@router.post("/workspace/active-project", response_model=WebActiveWorkspaceProjectResponse)
def web_set_active_nexa_workspace_project(
    body: WebSessionActiveProjectIn,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> WebActiveWorkspaceProjectResponse:
    sid = (body.session_id or "default").strip()[:64] or "default"
    cctx = get_or_create_context(db, app_user_id, web_session_id=sid)
    try:
        row = nxp_set_active(db, owner_user_id=app_user_id, cctx=cctx, project_id=body.project_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    pr_out = _nxp_out(row) if row is not None else None
    return WebActiveWorkspaceProjectResponse(
        ok=True,
        active_project_id=cctx.active_project_id,
        project=pr_out,
    )


@router.post("/workspace/roots/{root_id}/revoke", response_model=WebWorkspaceRootOut)
def web_revoke_workspace_root(
    root_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> WebWorkspaceRootOut:
    require_personal_workspace_mutation_allowed(db, app_user_id)
    r = wr_revoke_root(db, app_user_id, root_id)
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace root not found",
        )
    return WebWorkspaceRootOut(
        id=r.id,
        path_normalized=r.path_normalized,
        label=r.label,
        is_active=r.is_active,
        created_at=r.created_at,
    )
