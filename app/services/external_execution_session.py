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

    probe_markers = (
        "try for yourself",
        "try it yourself",
        "just try",
        "try yourself",
        "verify locally",
        "run the checks",
        "run checks",
        "run read-only",
        "run diagnostics",
        "check for yourself",
        "go ahead and check",
    )
    if any(m in t for m in probe_markers):
        out["permission_to_probe"] = True

    # Short grants → local CLI + probe (P0 operator-style; avoids “confirm again” loops)
    if re.search(r"\bcli\s+locally\b", t) or t.strip() in {"cli locally", "cli locally."}:
        out["auth_method"] = "local_cli"
        out["permission_to_probe"] = True
    if re.search(r"\buse\s+cli\b", t) and "don't use cli" not in t and "do not use cli" not in t:
        out["auth_method"] = "local_cli"
        out["permission_to_probe"] = True

    if re.search(r"\balready\s+authenticated\b", t) or "already logged in" in t:
        out["auth_method"] = "local_cli"
    if re.search(r"\blog(?:ged)?\s+in\s+locally\b", t) or ("logged in" in t and "local" in t):
        out["auth_method"] = "local_cli"
    if re.search(r"\bi\s*['']?m\s+logged\s+in\b", t) or re.search(r"\bi\s+am\s+logged\s+in\b", t):
        out["auth_method"] = "local_cli"
    if "railway is logged in" in t or "railway cli is logged in" in t or "logged into railway locally" in t:
        out["auth_method"] = "local_cli"
    if "railway login" in t or "use local cli" in t or "use railway cli" in t or ("cli" in t and "railway" in t):
        out["auth_method"] = "local_cli"
    if any(x in t for x in ("token set", "token is set", "have a token", "set railway token", "r railway_token")):
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

    if out.get("permission_to_probe") and out.get("auth_method") and not out.get("deploy_mode"):
        out["deploy_mode"] = "report_then_approve"

    # Granting probe permission in this flow means “use the CLI on this worker”.
    if out.get("permission_to_probe") and not out.get("auth_method"):
        out["auth_method"] = "local_cli"

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


def format_probe_readonly_intro() -> str:
    """Product copy — bounded read-only diagnostics only."""
    return (
        "Got it — I'll check your local Railway session now.\n\n"
        "I'll run read-only checks only:\n"
        "- `railway whoami`\n"
        "- `railway status`\n"
        "- `railway logs`\n"
        "- `git status`\n\n"
        "I will not deploy, push, or change anything without approval."
    )


def format_followup_acknowledgment(
    collected: dict[str, Any],
    *,
    db: Session | None,
    user_id: str | None,
) -> str:
    auth = (collected.get("auth_method") or "").strip()
    deploy = (collected.get("deploy_mode") or "").strip()
    uid = (user_id or "").strip()

    probe_intro = ""
    if collected.get("permission_to_probe"):
        probe_intro = format_probe_readonly_intro() + "\n\n---\n\n"

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
        "- inspect **hosted service status / logs** (Railway / Vercel / etc.) where the CLI allows\n"
        f"{path_hint}"
        "- diagnose what failed and summarize evidence-backed findings\n"
        f"{deploy_note}"
        "_Nothing here counts as a finished deploy — next messages should show real command output "
        "when runs occur._\n\n"
        "**Starting investigation now** — one moment while I align with your workspace and executor settings."
    )
    return (probe_intro + body).strip()


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

    prior_fc = dict(frag.get("collected") or {})
    collected = parse_followup_preferences(raw, prior_fc)
    # Never drop prefs already saved on the fragment (stops repeated confirmation).
    if prior_fc.get("auth_method") and not collected.get("auth_method"):
        collected["auth_method"] = prior_fc["auth_method"]
    if prior_fc.get("deploy_mode") and not collected.get("deploy_mode"):
        collected["deploy_mode"] = prior_fc["deploy_mode"]

    try:
        from app.core.config import get_settings

        op = bool(getattr(get_settings(), "nexa_operator_mode", False))
    except Exception:  # noqa: BLE001
        op = False

    if op:
        if collected.get("permission_to_probe") and not collected.get("auth_method"):
            collected["auth_method"] = "local_cli"
        if collected.get("auth_method") and not collected.get("deploy_mode"):
            collected.setdefault("deploy_mode", "report_then_approve")

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
    inv_block = ""
    try:
        from app.services.external_execution_runner import (
            format_investigation_for_chat,
            run_bounded_railway_repo_investigation,
        )

        inv = run_bounded_railway_repo_investigation(db, uid, collected)
        inv_block = format_investigation_for_chat(inv)
    except Exception as exc:  # noqa: BLE001
        logger.warning("external_execution.runner_failed uid=%s err=%s", uid, exc)
        inv_block = f"_Could not run bounded investigation on this host: {exc}_"

    full_reply = reply
    if (inv_block or "").strip():
        full_reply = f"{reply}\n\n---\n\n{inv_block.strip()}"

    _finalize_fragment_after_ack(db, cctx, collected)
    return {"mode": "chat", "text": full_reply, "intent": "external_execution_continue"}


def _cli_locally_grants_probe(text: str) -> bool:
    """Short replies like “CLI locally” grant local CLI + probe without extra confirmation."""
    t = (text or "").strip().lower()
    if re.search(r"\bcli\s+locally\b", t):
        return True
    if t.strip() in {"cli locally", "cli locally."}:
        return True
    if re.search(r"\buse\s+cli\b", t) and len(t) < 160:
        return True
    return False


def _user_claims_local_cli_auth(text: str) -> bool:
    t = (text or "").strip().lower()
    if _cli_locally_grants_probe(text):
        return True
    if re.search(r"\balready\s+authenticated\b", t):
        return True
    if "already logged in" in t:
        return True
    if re.search(r"\blog(?:ged)?\s+in\s+locally\b", t) or ("logged in" in t and "local" in t):
        return True
    if re.search(r"\bi\s*['']?m\s+logged\s+in\b", t) or re.search(r"\bi\s+am\s+logged\s+in\b", t):
        return True
    if "railway is logged in" in t or "railway cli is logged in" in t:
        return True
    if "logged into railway locally" in t or "logged in to railway locally" in t:
        return True
    if "railway login" in t or "use local cli" in t or "use railway cli" in t:
        return True
    if "cli" in t and "railway" in t:
        return True
    return False


def _user_requests_diagnostic_probe(text: str) -> bool:
    t = (text or "").strip().lower()
    markers = (
        "try for yourself",
        "try it yourself",
        "just try",
        "try yourself",
        "verify locally",
        "run the checks",
        "run checks",
        "run read-only",
        "run diagnostics",
        "check for yourself",
        "go ahead and check",
    )
    if any(m in t for m in markers):
        return True
    if "already authenticated" in t and "railway" in t:
        return True
    return False


def _snapshot_hints_railway_or_deploy(snap: dict[str, Any] | None) -> bool:
    if not snap:
        return False
    try:
        raw = json.dumps(snap, default=str).lower()
    except (TypeError, ValueError):
        return False
    keys = (
        "railway",
        "deploy",
        "render.com",
        "fly.io",
        "vercel",
        "external_execution",
        "hosted",
        "production",
        "nexa_missions",
    )
    return any(k in raw for k in keys)


def text_has_railway_execution_context(text: str, conversation_snapshot: dict[str, Any] | None) -> bool:
    """True when the turn or snapshot signals Railway / hosted execution context."""
    raw = (text or "").strip()
    from app.services.intent_focus_filter import extract_focused_intent
    from app.services.provider_router import should_skip_railway_bounded_path

    if extract_focused_intent(raw).get("ignore_railway"):
        return False
    if should_skip_railway_bounded_path(raw):
        logger.info("external_execution.railway_context_skipped vercel_dominant preview=%s", raw[:120])
        return False
    tl = raw.lower()
    if "railway" in tl:
        return True
    if re.search(r"https?://", tl):
        return True
    from app.services.intent_classifier import looks_like_external_execution, looks_like_external_investigation

    if looks_like_external_execution(raw) or looks_like_external_investigation(raw, conversation_snapshot):
        return True
    return _snapshot_hints_railway_or_deploy(conversation_snapshot)


def maybe_start_external_probe_from_turn(
    db: Session,
    user_id: str,
    user_text: str,
    cctx: ConversationContext,
    *,
    conversation_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Direct read-only probe when the user grants permission without an awaiting-followup session.

    Runs the same bounded Railway + git checks as the follow-up resume path.
    """
    uid = (user_id or "").strip()
    raw = (user_text or "").strip()
    if not uid or not raw:
        return None

    frag = get_external_execution_fragment(cctx)
    if frag and frag.get("status") == "awaiting_followup":
        return None

    if not _user_claims_local_cli_auth(raw):
        return None
    if not _user_requests_diagnostic_probe(raw) and not _cli_locally_grants_probe(raw):
        return None
    if not text_has_railway_execution_context(raw, conversation_snapshot):
        return None

    collected: dict[str, Any] = {
        "auth_method": "local_cli",
        "deploy_mode": "report_then_approve",
        "permission_to_probe": True,
    }
    intro = format_probe_readonly_intro()
    inv_block = ""
    try:
        from app.services.external_execution_runner import (
            format_investigation_for_chat,
            run_bounded_railway_repo_investigation,
        )

        inv = run_bounded_railway_repo_investigation(db, uid, collected)
        inv_block = format_investigation_for_chat(inv)
    except Exception as exc:  # noqa: BLE001
        logger.warning("external_execution.probe_runner_failed uid=%s err=%s", uid, exc)
        inv_block = f"_Could not run bounded investigation on this host: {exc}_"

    full_reply = intro
    if (inv_block or "").strip():
        full_reply = f"{intro}\n\n---\n\n{inv_block.strip()}"
    return {"mode": "chat", "text": full_reply, "intent": "external_execution_continue"}


def scrub_operator_idle_loop_phrases(text: str) -> str:
    """
    When ``NEXA_OPERATOR_MODE`` is set, tone down repeated confirmation nags in replies.

    Does not remove credential/setup blocks that contain tokens or compose instructions.
    """
    if not (text or "").strip():
        return text
    try:
        from app.core.config import get_settings

        if not bool(getattr(get_settings(), "nexa_operator_mode", False)):
            return text
    except Exception:  # noqa: BLE001
        return text

    out = re.sub(r"(?is)(\bconfirm again\b[\s\n]*){4,}", "Confirm once from the output above if needed.\n\n", text)
    return out


def scrub_generic_login_refusal_when_local_auth_claimed(reply: str, user_text: str) -> str:
    """
    Safety net: never show generic “cannot log in / paste output” coaching when the user
    explicitly claims local CLI auth and asks Nexa to verify on-host.
    """
    ut = (user_text or "").lower()
    claimed = (
        "already authenticated" in ut
        or "logged in locally" in ut
        or "try for yourself" in ut
        or "railway cli is logged in" in ut
        or "logged into railway locally" in ut
        or "use local cli" in ut
        or "use railway cli" in ut
    )
    if not claimed:
        return reply
    rl = (reply or "").lower()
    generic_refusal = (
        "cannot log in" in rl
        or "can't log in" in rl
        or "i can guide you" in rl
        or "paste the output" in rl
        or "i cannot log into your cloud" in rl
        or "can't log into your cloud" in rl
    )
    if not generic_refusal:
        return reply
    return (
        "I should try bounded read-only checks on this host first (`railway whoami`, `railway status`, "
        "`railway logs`, `git status`). If something prevents that, I'll report the exact blocker "
        "(missing CLI, host executor off, or no workspace path registered)."
    )


_RETRY_COMMAND_NORMALIZED = frozenset(
    {
        "retry external execution",
        "retry railway",
        "try again",
        "run the railway check again",
        "continue railway investigation",
    }
)


def is_retry_external_execution(text: str) -> bool:
    """Explicit retry phrases — must run bounded checks, not loop on placeholder copy."""
    raw = (text or "").strip().lower()
    raw = re.sub(r"[\s.!,;:]+$", "", raw)
    compact = " ".join(raw.split())
    return compact in _RETRY_COMMAND_NORMALIZED


def fragment_usable_for_retry(frag: dict[str, Any] | None) -> bool:
    """Saved external-exec flow exists (ignore TTL when user explicitly retries)."""
    if not isinstance(frag, dict):
        return False
    return frag.get("status") in ("completed", "awaiting_followup")


def collected_for_external_execution_retry(
    db: Session,
    user_id: str,
    frag: dict[str, Any],
) -> dict[str, Any]:
    """Merge saved prefs with safe defaults for a retry run."""
    from app.services.external_execution_access import assess_external_execution_access

    prior_raw = frag.get("collected")
    prior: dict[str, Any] = dict(prior_raw) if isinstance(prior_raw, dict) else {}
    acc = assess_external_execution_access(db, user_id)

    auth = (prior.get("auth_method") or "").strip()
    if not auth:
        auth = "token_env" if acc.railway_token_present else "local_cli"

    deploy = (prior.get("deploy_mode") or "").strip() or "report_then_approve"
    out = {**prior, "auth_method": auth, "deploy_mode": deploy}
    out["permission_to_probe"] = True
    return out


def format_retry_investigation_intro() -> str:
    stamp = _utc_now_iso()
    return (
        f"Retrying Railway investigation _(run at {stamp})_...\n\n"
        "Read-only checks only:\n"
        "- `railway whoami`\n"
        "- `railway status`\n"
        "- `railway logs`\n"
        "- `git status`\n\n"
        "No deploy, push, or file changes will run."
    )


def try_retry_external_execution_turn(
    db: Session,
    user_id: str,
    user_text: str,
    cctx: ConversationContext,
) -> dict[str, Any] | None:
    """
    Handle explicit **retry external execution** — runs bounded Railway/repo investigation.

    Must run before :func:`try_resume_external_execution_turn` so retry is not misparsed as prefs text.
    """
    if not is_retry_external_execution(user_text):
        return None
    uid = (user_id or "").strip()
    if not uid:
        return None

    frag = get_external_execution_fragment(cctx)
    if not fragment_usable_for_retry(frag):
        logger.info(
            "RETRY_TRIGGERED user_id=%s fragment_present=False fragment_status=None — no usable saved flow",
            uid,
        )
        return {
            "mode": "chat",
            "text": (
                "I don't have a saved Railway investigation to retry.\n\n"
                "Send the Railway project URL and repo path again, and I'll start a fresh read-only investigation."
            ),
            "intent": "external_execution_continue",
        }

    from app.services.external_execution_access import assess_external_execution_access
    from app.services.external_execution_credentials import format_railway_token_not_loaded_retry_reply

    acc = assess_external_execution_access(db, uid)
    if not acc.railway_access_available:
        logger.info("RETRY_BLOCKED user_id=%s railway_access_available=False", uid)
        return {
            "mode": "chat",
            "text": format_railway_token_not_loaded_retry_reply(),
            "intent": "external_execution_continue",
        }

    logger.info(
        "RETRY_TRIGGERED user_id=%s fragment_status=%s fragment_keys=%s",
        uid,
        (frag or {}).get("status"),
        sorted((frag or {}).keys()),
    )

    collected = collected_for_external_execution_retry(db, uid, frag)
    logger.info(
        "RETRY_RUNNER_START user_id=%s auth_method=%s deploy_mode=%s permission_to_probe=%s",
        uid,
        collected.get("auth_method"),
        collected.get("deploy_mode"),
        collected.get("permission_to_probe"),
    )

    intro = format_retry_investigation_intro()
    inv_block = ""
    try:
        from app.services.external_execution_runner import (
            format_investigation_for_chat,
            investigation_to_public_payload,
            run_bounded_railway_repo_investigation,
        )

        inv = run_bounded_railway_repo_investigation(db, uid, collected)
        payload = investigation_to_public_payload(inv)
        logger.info(
            "RETRY_RUNNER_RESULT user_id=%s ran=%s reason=%s skipped_reason=%s",
            uid,
            payload.get("ran"),
            payload.get("reason"),
            inv.skipped_reason,
        )
        inv_block = format_investigation_for_chat(inv)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "RETRY_RUNNER_EXCEPTION user_id=%s err=%s",
            uid,
            exc,
            exc_info=True,
        )
        inv_block = (
            "### Retry could not complete\n\n"
            f"I attempted the read-only investigation but hit an error: `{exc}`\n\n"
            "**What to check:** host executor (`NEXA_HOST_EXECUTOR_ENABLED`), a registered dev workspace path, "
            "and Railway CLI or `RAILWAY_TOKEN` on this worker."
        )

    full_reply = intro
    if (inv_block or "").strip():
        full_reply = f"{intro}\n\n---\n\n{inv_block.strip()}"
    else:
        logger.warning(
            "RETRY_EMPTY_OUTPUT user_id=%s — forcing blocker message",
            uid,
        )
        full_reply = (
            f"{intro}\n\n---\n\n"
            "### No output produced\n\n"
            "The runner returned no diagnostic block; check logs for `RETRY_RUNNER_RESULT` / host executor / workspace."
        )
    return {"mode": "chat", "text": full_reply, "intent": "external_execution_continue"}


__all__ = [
    "collected_for_external_execution_retry",
    "format_retry_investigation_intro",
    "fragment_usable_for_retry",
    "is_retry_external_execution",
    "mark_external_execution_awaiting_followup",
    "maybe_start_external_probe_from_turn",
    "try_resume_external_execution_turn",
    "try_retry_external_execution_turn",
    "get_external_execution_fragment",
    "clear_external_execution_fragment",
    "parse_followup_preferences",
    "scrub_generic_login_refusal_when_local_auth_claimed",
    "scrub_operator_idle_loop_phrases",
    "format_probe_readonly_intro",
]
