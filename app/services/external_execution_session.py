"""
Cross-turn state for external execution asks (Railway / deploy pipelines).

Persists under ConversationContext.current_flow_state_json["external_execution"]
without replacing unrelated lightweight-workflow data.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.conversation_context import ConversationContext
from app.services.dev_runtime.workspace import list_workspaces

logger = logging.getLogger(__name__)

FLOW_SUBKEY = "external_execution"
TTL_SECONDS = 45 * 60


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_top_level(raw: str | None) -> dict[str, Any]:
    if not (raw or "").strip():
        return {}
    try:
        o = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return o if isinstance(o, dict) else {}


def get_external_execution_fragment(cctx: ConversationContext) -> dict[str, Any] | None:
    st = _load_top_level(cctx.current_flow_state_json)
    ex = st.get(FLOW_SUBKEY)
    return ex if isinstance(ex, dict) else None


def _fragment_expired(frag: dict[str, Any]) -> bool:
    u = str(frag.get("updated_at") or frag.get("prompted_at") or "")
    if not u:
        return True
    try:
        t = datetime.fromisoformat(u.replace("Z", "+00:00"))
    except ValueError:
        return True
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() > TTL_SECONDS


def clear_external_execution_fragment(db: Session, cctx: ConversationContext) -> None:
    st = _load_top_level(cctx.current_flow_state_json)
    if FLOW_SUBKEY in st:
        del st[FLOW_SUBKEY]
        cctx.current_flow_state_json = json.dumps(st, ensure_ascii=False)[:20_000] if st else None
        db.add(cctx)
        db.commit()


def mark_external_execution_awaiting_followup(
    db: Session | None,
    user_id: str | None,
    cctx: ConversationContext | None,
    *,
    gated: bool,
) -> None:
    """After Nexa prompts for access/prefs, remember so the next user turn can resume."""
    uid = (user_id or "").strip()
    if db is None or not uid:
        return
    try:
        from app.services.conversation_context_service import get_or_create_context

        row = cctx if cctx is not None else get_or_create_context(db, uid)
        st = _load_top_level(row.current_flow_state_json)
        frag = {
            "status": "awaiting_followup",
            "phase": "access_required" if gated else "capabilities_ok",
            "gated": bool(gated),
            "collected": {},
            "prompted_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
        }
        st[FLOW_SUBKEY] = frag
        row.current_flow_state_json = json.dumps(st, ensure_ascii=False)[:20_000]
        db.add(row)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("external_execution.mark_awaiting_failed uid=%s err=%s", uid, exc)
        try:
            db.rollback()
        except Exception:
            pass


def parse_followup_preferences(text: str, collected: dict[str, Any]) -> dict[str, Any]:
    """Merge NL prefs into collected auth/deploy fields."""
    out = dict(collected)
    t = (text or "").strip().lower()

    if re.search(r"\blog(?:ged)?\s+in\s+locally\b", t) or (
        "logged in" in t and "local" in t
    ):
        out["auth_method"] = "local_cli"
    elif "railway login" in t or ("cli" in t and "railway" in t):
        out["auth_method"] = "local_cli"
    elif any(x in t for x in ("token set", "token is set", "have a token", "set railway token", "r railway_token")):
        out["auth_method"] = "token_env"

    if any(
        x in t
        for x in (
            "report findings first",
            "findings first",
            "report first",
            "diagnose first",
            "analysis first",
            "no deploy yet",
            "don't deploy",
            "do not deploy",
            "dont deploy",
            "not deploy",
            "ask before deploy",
            "before deploying",
            "before you deploy",
            "approve deploy",
            "confirm deploy",
        )
    ):
        out["deploy_mode"] = "report_then_approve"
    if any(x in t for x in ("go ahead and deploy", "deploy when ready", "ship it", "you can deploy")):
        out["deploy_mode"] = "deploy_when_ready"

    return out


def _workspace_repo_hint(db: Session, user_id: str) -> str | None:
    try:
        rows = list_workspaces(db, user_id)
    except Exception:
        return None
    if len(rows) != 1:
        return None
    rp = getattr(rows[0], "repo_path", None)
    if rp and str(rp).strip():
        return str(rp).strip()
    return None


def _finalize_fragment_after_ack(db: Session, cctx: ConversationContext, collected: dict[str, Any]) -> None:
    st = _load_top_level(cctx.current_flow_state_json)
    frag = st.get(FLOW_SUBKEY) if isinstance(st.get(FLOW_SUBKEY), dict) else {}
    frag["status"] = "completed"
    frag["collected"] = collected
    frag["updated_at"] = _utc_now_iso()
    st[FLOW_SUBKEY] = frag
    cctx.current_flow_state_json = json.dumps(st, ensure_ascii=False)[:20_000]
    db.add(cctx)
    db.commit()


def format_followup_acknowledgment(
    collected: dict[str, Any],
    *,
    db: Session | None,
    user_id: str | None,
) -> str:
    auth = (collected.get("auth_method") or "").strip()
    deploy = (collected.get("deploy_mode") or "").strip()
    uid = (user_id or "").strip()

    auth_line = (
        "use your **local Railway CLI** session (logged in on this machine)"
        if auth == "local_cli"
        else (
            "use **Railway token / API** credentials you configured for this worker"
            if auth == "token_env"
            else "use whichever Railway access you have configured (CLI or token)"
        )
    )

    path_hint = ""
    if db is not None and uid:
        p = _workspace_repo_hint(db, uid)
        if p:
            path_hint = f"- inspect / work in your registered repo at `{p}`\n"

    deploy_note = ""
    if deploy == "report_then_approve":
        deploy_note = (
            "\nI will **not** deploy yet — I’ll **report findings first**, then ask before any deploy.\n"
        )
    elif deploy == "deploy_when_ready":
        deploy_note = "\nI’ll **prepare** changes and only deploy when you clearly confirm.\n"
    else:
        deploy_note = (
            "\nI’ll **prioritize diagnosis and a clear report** before suggesting deploy steps.\n"
        )

    body = (
        "Got it.\n\n"
        "Next I’ll:\n"
        f"- {auth_line}\n"
        "- inspect **Railway service status / logs** where the CLI allows\n"
        f"{path_hint}"
        "- diagnose what failed and summarize evidence-backed findings\n"
        f"{deploy_note}"
        "_Nothing here counts as a finished deploy — next messages should show real command output "
        "when runs occur._\n\n"
        "**Starting investigation now** — one moment while I align with your workspace and executor settings."
    )
    return body.strip()


def _user_aborts_flow(text: str) -> bool:
    t = (text or "").strip().lower()
    if len(t) > 120:
        return False
    return bool(
        re.search(
            r"(?i)^(cancel|never mind|forget it|stop|abort)(\s|$|[,.!])",
            t,
        )
    )


def try_resume_external_execution_turn(
    db: Session,
    user_id: str,
    user_text: str,
    cctx: ConversationContext,
) -> dict[str, Any] | None:
    """
    If we previously prompted for external-exec access/prefs, interpret this message as the answer.

    Returns a gateway payload dict, or None to continue normal routing.
    """
    uid = (user_id or "").strip()
    raw = (user_text or "").strip()
    if not uid or not raw:
        return None

    frag = get_external_execution_fragment(cctx)
    if not frag or frag.get("status") != "awaiting_followup":
        return None
    if _fragment_expired(frag):
        clear_external_execution_fragment(db, cctx)
        return None

    if _user_aborts_flow(raw):
        clear_external_execution_fragment(db, cctx)
        return {
            "mode": "chat",
            "text": (
                "Understood — I’ve cleared the pending Railway / deploy follow-up. "
                "Tell me what you’d like to do next."
            ),
            "intent": "external_execution_continue",
        }

    collected = parse_followup_preferences(raw, dict(frag.get("collected") or {}))
    has_auth = bool(collected.get("auth_method"))
    has_deploy = bool(collected.get("deploy_mode"))

    if not has_auth and not has_deploy:
        reply = (
            "I want to align with your setup — please confirm:\n"
            "- Railway: **CLI logged in locally** on this machine, **or** token env vars?\n"
            "- Deploy: **report findings first** (no deploy until you approve), or ok to deploy after fixes?\n\n"
            "Short reply is fine (e.g. “CLI locally, report first”)."
        )
        st = _load_top_level(cctx.current_flow_state_json)
        ex = dict(st.get(FLOW_SUBKEY) or {})
        ex["status"] = "awaiting_followup"
        ex["collected"] = collected
        ex["updated_at"] = _utc_now_iso()
        st[FLOW_SUBKEY] = ex
        cctx.current_flow_state_json = json.dumps(st, ensure_ascii=False)[:20_000]
        db.add(cctx)
        db.commit()
        return {"mode": "chat", "text": reply, "intent": "external_execution_continue"}

    reply = format_followup_acknowledgment(collected, db=db, user_id=uid)
    _finalize_fragment_after_ack(db, cctx, collected)
    return {"mode": "chat", "text": reply, "intent": "external_execution_continue"}


__all__ = [
    "mark_external_execution_awaiting_followup",
    "try_resume_external_execution_turn",
    "get_external_execution_fragment",
    "clear_external_execution_fragment",
    "parse_followup_preferences",
]
