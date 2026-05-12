# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Natural-language host executor offers: confirm once, then enqueue approved jobs only."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.conversation_context import ConversationContext
from app.repositories.telegram_repo import TelegramRepository
from app.schemas.agent_job import AgentJobCreate
from app.services.agent_job_service import AgentJobService
from app.services.content_provenance import InstructionSource, apply_trusted_instruction_source
from app.services.custom_agent_routing import custom_agent_message_blocks_folder_heuristics
from app.services.host_executor import (
    ALLOWED_RUN_COMMANDS,
    execute_payload,
    is_command_safe,
    proposed_risk_level,
)
from app.services.host_executor_intent import (
    infer_host_executor_action,
    safe_relative_path,
    title_for_payload,
)
from app.services.input_secret_guard import secret_paste_chat_reply, user_message_contains_inline_secret
from app.services.local_file_intent import infer_local_file_request
from app.services.nexa_safety_policy import stamp_host_payload
from app.services.nexa_workspace_project_registry import (
    active_project_relative_base,
    merge_payload_with_project_base,
)


def _secret_guard_reply_if_needed(user_text: str):
    """Block host/path routing when the user pasted env keys or token-like secrets."""
    if not user_message_contains_inline_secret(user_text):
        return None
    from app.services.next_action_apply import NextActionApplicationResult

    return NextActionApplicationResult(
        secret_paste_chat_reply(),
        user_text,
        False,
        True,
        None,
    )


def _agent_team_chat_blocks_folder_heuristics(text: str) -> bool:
    """Lazy import: avoids import cycle (agent_team.chat → service → host_bridge → this module)."""
    from app.services.agent_team.chat import agent_team_chat_blocks_folder_heuristics

    return agent_team_chat_blocks_folder_heuristics(text)
from app.services.host_executor_visibility import (
    completion_system_event_text,
    format_host_completion_message,
    format_host_confirmation,
    format_queued_ack,
)
from app.services.next_action_confirmation import (
    _wants_proceed_ok,
    _wants_yesish,
    is_pending_inject_expired,
)
from app.services.permission_request_flow import (
    card_message_for_host_payload,
    derive_permission_reason,
    is_permission_eligible_precheck_failure,
    is_permission_row_denied,
    permission_fields_for_enqueue_payload,
    permission_required_payload,
    precheck_host_executor_permissions,
    reason_for_host_payload,
    request_permission_from_chat,
    still_waiting_permission_message,
)

logger = logging.getLogger(__name__)

_PENDING_KIND = "host_executor"

# Compare user-inferred host payloads to blocked JSON without policy/chat metadata (stamped at enqueue).
_META_HOST_PAYLOAD_KEYS = frozenset(
    {
        "nexa_safety_policy_version",
        "nexa_safety_policy_sha256",
        "nexa_safety_policy_version_int",
        "instruction_source",
        "chat_origin",
        "chat_pending_title",
        "web_chat_notified",
    }
)


def _host_payload_semantic_for_compare(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if k not in _META_HOST_PAYLOAD_KEYS}


def _legacy_command_pending(pending_json: str | None) -> bool:
    if not (pending_json or "").strip():
        return False
    try:
        o = json.loads(pending_json)
    except (json.JSONDecodeError, TypeError, ValueError):
        return False
    if not isinstance(o, dict):
        return False
    return bool(str(o.get("command") or "").strip())


def may_run_pre_llm_deterministic_host(cctx: ConversationContext) -> bool:
    """
    When False, blocked state or host confirmation pending owns this turn — do not infer a new
    host action / permission request (handled inside try_apply_host_executor_turn).
    """
    if _legacy_command_pending(cctx.next_action_pending_inject_json):
        return False
    if (getattr(cctx, "blocked_host_executor_json", None) or "").strip():
        return False
    if _parse_pending_host_executor(cctx.next_action_pending_inject_json):
        return False
    return True


def _parse_pending_host_executor(
    pending_json: str | None,
) -> tuple[dict[str, Any], str] | None:
    if not (pending_json or "").strip():
        return None
    try:
        o = json.loads(pending_json)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(o, dict):
        return None
    if (o.get("kind") or "").strip() != _PENDING_KIND:
        return None
    payload = o.get("payload")
    if not isinstance(payload, dict):
        return None
    title = str(o.get("title") or title_for_payload(payload)).strip() or title_for_payload(
        payload
    )
    return payload, title


def _confirms_host_executor(user_text: str) -> bool:
    tl = (user_text or "").strip().lower()
    if tl in ("continue", "do it", "do that", "run it", "go ahead", "run"):
        return True
    return bool(_wants_yesish(user_text) or _wants_proceed_ok(user_text))


def _declines_host_executor(user_text: str) -> bool:
    tl = (user_text or "").strip().lower()
    return bool(
        re.match(
            r"^(no|nope|cancel|abort|never-?mind|forget\s+it|don\'t|dont)\b",
            tl,
        )
    )


def _telegram_chat_id(db: Session, app_user_id: str) -> str | None:
    link = TelegramRepository().get_by_app_user(db, app_user_id)
    if link and link.chat_id is not None:
        return str(link.chat_id)
    return None


def _validate_enqueue_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Ensure dict matches allowed host_action shapes (same allowlist as host_executor)."""

    def _attach_cwd(out: dict[str, Any]) -> dict[str, Any]:
        cwd = str(payload.get("cwd_relative") or "").strip()
        if cwd:
            sr = safe_relative_path(cwd.replace("\\", "/"))
            if sr:
                out = dict(out)
                out["cwd_relative"] = sr
        return out

    act = (payload.get("host_action") or "").strip().lower()
    if act == "git_status":
        return _attach_cwd({"host_action": "git_status"})
    if act == "run_command":
        rn = (payload.get("run_name") or "").strip().lower()
        if rn in ALLOWED_RUN_COMMANDS:
            return _attach_cwd({"host_action": "run_command", "run_name": rn})
        cmd = str(payload.get("command") or "").strip()
        if cmd and is_command_safe(cmd):
            out_rc = {
                "host_action": "run_command",
                "command": cmd,
                "command_type": str(payload.get("command_type") or "").strip()[:80],
            }
            return _attach_cwd(out_rc)
        return None
    if act == "file_read":
        rel = safe_relative_path(str(payload.get("relative_path") or ""))
        if rel:
            return _attach_cwd({"host_action": "file_read", "relative_path": rel})
        return None
    if act == "file_write":
        rel = safe_relative_path(str(payload.get("relative_path") or ""))
        content = payload.get("content")
        if rel and content is not None:
            return _attach_cwd({"host_action": "file_write", "relative_path": rel, "content": content})
        return None
    if act == "list_directory":
        rp = (payload.get("relative_path") or ".").strip() or "."
        rel = safe_relative_path(rp) if rp != "." else "."
        if not rel:
            return None
        out_ld: dict[str, Any] = {"host_action": "list_directory", "relative_path": rel}
        raw_abs = payload.get("nexa_permission_abs_targets")
        if isinstance(raw_abs, list) and raw_abs:
            cleaned: list[str] = []
            for x in raw_abs[:8]:
                xs = str(x).strip()
                if xs:
                    cleaned.append(xs)
            if cleaned:
                out_ld["nexa_permission_abs_targets"] = cleaned
        return _attach_cwd(out_ld)
    if act == "find_files":
        rp = (payload.get("relative_path") or ".").strip() or "."
        rel = safe_relative_path(rp) if rp != "." else "."
        if not rel:
            return None
        glob = str(payload.get("glob") or payload.get("pattern") or "*").strip()[:120]
        return _attach_cwd({"host_action": "find_files", "relative_path": rel, "glob": glob or "*"})
    if act == "git_commit":
        msg = str(payload.get("commit_message") or "").strip()
        if not msg or len(msg) > 240:
            return None
        return _attach_cwd({"host_action": "git_commit", "commit_message": msg})

    if act == "git_push":
        pr = str(payload.get("push_remote") or "").strip()
        pf = str(payload.get("push_ref") or "").strip()
        out_gp: dict[str, Any] = {"host_action": "git_push"}
        if pr:
            out_gp["push_remote"] = pr[:64]
        if pf:
            out_gp["push_ref"] = pf[:200]
        return _attach_cwd(out_gp)

    if act == "vercel_projects_list":
        return _attach_cwd({"host_action": "vercel_projects_list"})

    if act == "vercel_remove":
        pn = str(payload.get("vercel_project_name") or payload.get("project_name") or "").strip()
        if not pn or payload.get("vercel_yes") is not True:
            return None
        out_rm: dict[str, Any] = {
            "host_action": "vercel_remove",
            "vercel_project_name": pn[:100],
            "vercel_yes": True,
        }
        return _attach_cwd(out_rm)

    if act == "read_multiple_files":
        raw_list = payload.get("relative_paths")
        if isinstance(raw_list, list) and raw_list:
            cleaned: list[str] = []
            for x in raw_list[:21]:
                sp = safe_relative_path(str(x))
                if sp:
                    cleaned.append(sp)
            if not cleaned:
                return None
            out: dict[str, Any] = {
                "host_action": "read_multiple_files",
                "relative_paths": cleaned[:20],
            }
            if payload.get("intel_analysis"):
                out["intel_analysis"] = True
                out["intel_question"] = str(payload.get("intel_question") or "")[:2000]
                out["intel_operation"] = str(payload.get("intel_operation") or "summarize")[:48]
            return _attach_cwd(out)
        rd = str(payload.get("relative_path") or payload.get("relative_dir") or ".").strip() or "."
        rel = safe_relative_path(rd) if rd != "." else "."
        if not rel:
            return None
        out2: dict[str, Any] = {"host_action": "read_multiple_files", "relative_path": rel}
        gp = str(payload.get("glob") or "").strip()
        if gp:
            out2["glob"] = gp[:120]
        kw = str(payload.get("keyword") or "").strip()
        if kw:
            out2["keyword"] = kw[:200]
        exts = payload.get("extensions")
        if isinstance(exts, list) and exts:
            out2["extensions"] = [str(e).strip()[:16] for e in exts[:24] if str(e).strip()]
        raw_abs_rm = payload.get("nexa_permission_abs_targets")
        if isinstance(raw_abs_rm, list) and raw_abs_rm:
            cleaned_rm: list[str] = []
            for x in raw_abs_rm[:8]:
                xs = str(x).strip()
                if xs:
                    cleaned_rm.append(xs)
            if cleaned_rm:
                out2["nexa_permission_abs_targets"] = cleaned_rm
                try:
                    # Invariant: base ⇔ nexa_permission_abs_targets[0] (canonical resolved path).
                    out2["base"] = str(Path(str(cleaned_rm[0])).expanduser().resolve())[:8000]
                except OSError:
                    return None
        if "base" not in out2:
            try:
                wr = Path(get_settings().host_executor_work_root).expanduser().resolve()
                out2["base"] = str((wr / rel.replace("\\", "/")).resolve())[:8000]
            except OSError:
                pass
            if "base" not in out2:
                bs = payload.get("base")
                if bs:
                    out2["base"] = str(bs).strip()[:8000]
        if payload.get("intel_analysis"):
            out2["intel_analysis"] = True
            out2["intel_question"] = str(payload.get("intel_question") or "")[:2000]
            out2["intel_operation"] = str(payload.get("intel_operation") or "summarize")[:48]
        return _attach_cwd(out2)

    if act == "chain":
        from app.services.host_executor_chain import parse_chain_inner_allowed

        s = get_settings()
        if not bool(getattr(s, "nexa_host_executor_chain_enabled", False)):
            return None
        allowed = parse_chain_inner_allowed(s)
        actions_in = payload.get("actions")
        if not isinstance(actions_in, list) or not actions_in:
            return None
        max_s = min(max(int(getattr(s, "nexa_host_executor_chain_max_steps", 10)), 1), 20)
        if len(actions_in) > max_s:
            return None
        for step in actions_in:
            if not isinstance(step, dict):
                return None
            sha = (step.get("host_action") or "").strip().lower()
            if sha == "chain" or sha not in allowed:
                return None
        out_ch: dict[str, Any] = {"host_action": "chain", "actions": list(actions_in)}
        stp = payload.get("stop_on_failure")
        if isinstance(stp, bool):
            out_ch["stop_on_failure"] = stp
        return _attach_cwd(out_ch)

    return None


def enqueue_host_job_from_validated_payload(
    db: Session,
    app_user_id: str,
    *,
    safe_pl: dict[str, Any],
    title: str,
    web_session_id: str,
    access_permission_resume: bool = False,
    permission_request_id: int | None = None,
    permission_scope: str | None = None,
    permission_target: str | None = None,
    agent_assignment_id: int | None = None,
):
    """Shared enqueue path after validation (confirm flow + permission-resume API).

    When ``access_permission_resume`` is True, the access-permission dialog already approved
    this host action — create the job as **queued** so ``local_tool_worker`` can pick it up.
    Otherwise host-executor jobs stay ``needs_approval`` for the Job-tab approval step.
    """
    wid = (web_session_id or "default").strip()[:64] or "default"
    chat_origin: dict[str, Any] = {"web_session_id": wid, "conversation_id": wid}
    if agent_assignment_id is not None:
        chat_origin["agent_assignment_id"] = str(int(agent_assignment_id))
    if permission_request_id is not None:
        chat_origin["permission_request_id"] = str(int(permission_request_id))
    if permission_scope:
        chat_origin["permission_scope"] = str(permission_scope)[:128]
    if permission_target:
        chat_origin["permission_target"] = str(permission_target)[:8000]
    full_payload = stamp_host_payload(
        apply_trusted_instruction_source(
            {
                **safe_pl,
                "chat_origin": chat_origin,
                "chat_pending_title": title,
                "web_chat_notified": False,
            },
            InstructionSource.USER_MESSAGE.value,
        )
    )
    jobs = AgentJobService()
    resume_note = (
        "Auto-approved — running now."
        if access_permission_resume
        else "Waiting for your approval in the Jobs tab before running."
    )
    job = jobs.create_job(
        db,
        app_user_id,
        AgentJobCreate(
            kind="local_action",
            worker_type="local_tool",
            title=title_for_payload(safe_pl)[:255],
            instruction=f"Host tool: {title}. {resume_note}",
            command_type="host-executor",
            payload_json=full_payload,
            source="chat",
            telegram_chat_id=_telegram_chat_id(db, app_user_id),
            approval_required=False if access_permission_resume else None,
        ),
    )
    risk = proposed_risk_level(safe_pl)
    jobs.repo.update(db, job, risk_level=risk)
    act = (safe_pl.get("host_action") or "").strip().lower()
    if act == "chain":
        actions_in = safe_pl.get("actions")
        inner = (
            [
                (a.get("host_action") if isinstance(a, dict) else None)
                for a in (actions_in if isinstance(actions_in, list) else [])
            ]
        )
        logger.info(
            "Chain job queued for approval id=%s steps=%s user=%s",
            job.id,
            len(inner),
            app_user_id,
            extra={
                "nexa_event": "chain_job_queued",
                "job_id": job.id,
                "chain_length": len(inner),
                "telegram_chat_id": job.telegram_chat_id,
                "inner_actions": inner,
            },
        )
    else:
        logger.info(
            "host_executor queued job id=%s user=%s action=%s",
            job.id,
            app_user_id,
            safe_pl.get("host_action"),
        )
    return job


def _set_host_pending(cctx: ConversationContext, payload: dict[str, Any], title: str) -> None:
    stamped = stamp_host_payload(dict(payload))
    cctx.next_action_pending_inject_json = json.dumps(
        {
            "kind": _PENDING_KIND,
            "payload": stamped,
            "title": title,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
    )


def evaluate_deterministic_host_permission_turn(
    db: Session,
    cctx: ConversationContext,
    user_text: str,
    *,
    web_session_id: str | None = None,
    simulate_mode: bool = False,
    simulate_execute_text: str | None = None,
):
    """
    Stateless host intent → permission check → missing-grant request / confirmation.

    Does not handle blocked_host_executor_json, pending inject, or confirm/queue branches.
    Used when we must enforce permission lifecycle without falling through to the LLM.
    """
    from app.services.next_action_apply import NextActionApplicationResult

    t0 = (user_text or "").strip()
    if not t0:
        return None

    sg0 = _secret_guard_reply_if_needed(t0)
    if sg0 is not None:
        return sg0

    if custom_agent_message_blocks_folder_heuristics(t0) or _agent_team_chat_blocks_folder_heuristics(
        t0
    ):
        return None

    if _legacy_command_pending(cctx.next_action_pending_inject_json):
        return None

    if not get_settings().nexa_host_executor_enabled:
        return None

    base = active_project_relative_base(db, (cctx.user_id or "").strip(), cctx)
    inferred = infer_host_executor_action(t0)
    if not inferred:
        from app.services.host_executor_nl_chain import try_infer_browser_automation_nl

        inferred = try_infer_browser_automation_nl(t0)
    if not inferred:
        from app.services.host_executor_nl_chain import try_infer_readme_push_chain_nl

        inferred = try_infer_readme_push_chain_nl(t0)
    if not inferred:
        lf = infer_local_file_request(t0, default_relative_base=base)
        if lf.matched and lf.error_message:
            return NextActionApplicationResult(
                lf.error_message,
                t0,
                False,
                True,
                None,
            )
        if lf.matched and lf.clarification_message:
            return NextActionApplicationResult(
                lf.clarification_message,
                t0,
                False,
                True,
                None,
            )
        if lf.matched and lf.path_resolution_failed:
            return NextActionApplicationResult(
                "That folder isn’t under Nexa’s configured host work root (`HOST_EXECUTOR_WORK_ROOT`). "
                "Adjust the work root to include it, register it with `/workspace add`, then ask again.",
                t0,
                False,
                True,
                None,
            )
        if lf.matched and lf.payload:
            inferred = lf.payload
    if not inferred:
        return None

    if base != ".":
        inferred = merge_payload_with_project_base(inferred, base)

    inferred = apply_trusted_instruction_source(
        dict(inferred), InstructionSource.USER_MESSAGE.value
    )

    title = title_for_payload(inferred)
    uid = (cctx.user_id or "").strip()
    ok_pre, err_pre = precheck_host_executor_permissions(db, uid, inferred)
    if not ok_pre:
        if is_permission_eligible_precheck_failure(err_pre, inferred):
            scope_t, target_t, risk_t = permission_fields_for_enqueue_payload(inferred)
            reason_t = derive_permission_reason(
                scope_t, reason_override=reason_for_host_payload(inferred)
            )
            stamped_infer = stamp_host_payload(
                apply_trusted_instruction_source(
                    dict(inferred), InstructionSource.USER_MESSAGE.value
                )
            )
            ws_id = (
                web_session_id or getattr(cctx, "session_id", None) or "default"
            ).strip()[:64]
            msg_pr, row_pr, _reused = request_permission_from_chat(
                db,
                uid,
                scope=scope_t,
                target=target_t,
                risk_level=risk_t,
                reason=reason_t,
                metadata={"host_action": (inferred.get("host_action") or "")[:64]},
                pending_payload=stamped_infer,
                pending_title=title,
                web_session_id=ws_id,
            )
            cctx.blocked_host_executor_json = json.dumps(
                {
                    "payload": stamped_infer,
                    "title": title,
                    "permission_id": row_pr.id,
                },
                ensure_ascii=False,
            )[:20_000]
            db.add(cctx)
            db.commit()
            pr_line = card_message_for_host_payload(inferred)
            perm_req = permission_required_payload(
                permission_request_id=row_pr.id,
                scope=scope_t,
                target=target_t,
                reason=reason_t,
                risk_level=risk_t,
                message=pr_line,
            )
            return NextActionApplicationResult(
                msg_pr,
                t0,
                False,
                True,
                None,
                permission_required=perm_req,
            )
        return NextActionApplicationResult(
            (err_pre or "That path isn’t allowed for host actions.")[:3500],
            t0,
            False,
            True,
            None,
        )

    if simulate_mode:
        from app.services.host_executor import build_simulation_plan

        if not bool(getattr(get_settings(), "nexa_simulation_enabled", True)):
            return None
        stamped_sim = stamp_host_payload(dict(inferred))
        safe_sim = _validate_enqueue_payload(stamped_sim)
        if not safe_sim:
            return NextActionApplicationResult(
                "Simulation: could not validate that host action payload.",
                t0,
                False,
                True,
                None,
            )

        class _StubJob:
            user_id = uid
            payload_json: dict[str, Any] = {}

        stub = _StubJob()
        try:
            plan_txt = execute_payload(safe_sim, db=db, job=stub, simulate=True)
        except ValueError as exc:
            return NextActionApplicationResult(
                f"Simulation (validation): {exc}",
                t0,
                False,
                True,
                None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("simulate_mode execute_payload failed", exc_info=True)
            return NextActionApplicationResult(
                f"Simulation failed: {exc!s}",
                t0,
                False,
                True,
                None,
            )
        try:
            structured = build_simulation_plan(safe_sim)
        except Exception as exc:  # noqa: BLE001
            structured = {"action": "(error)", "fields": {"error": str(exc)[:200]}}

        summary_lines = [
            "🔍 Simulation (nothing executed yet)",
            "",
            (plan_txt or "")[:2800],
            "",
            f"action={structured.get('action')} · kind={structured.get('kind')}",
        ]
        diff_u = None
        if isinstance(structured.get("diff"), dict):
            diff_u = structured["diff"].get("unified")
        if diff_u:
            prev_lines = str(diff_u).splitlines()[:24]
            summary_lines.extend(["", "Diff preview (truncated):", *prev_lines])

        exec_store = (simulate_execute_text or "").strip() or t0
        cctx.simulate_execute_pending_json = json.dumps(
            {
                "execute_text": exec_store,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        )
        db.add(cctx)
        db.commit()

        kb_rows: tuple[tuple[tuple[str, str], ...], ...] = (
            (("✅ Approve & Execute", "simtxt:exec"),),
        )
        return NextActionApplicationResult(
            "\n".join(summary_lines)[:3900],
            t0,
            False,
            True,
            None,
            telegram_inline_keyboard_rows=kb_rows,
        )

    from app.services.user_capabilities import is_privileged_owner_for_web_mutations

    if bool(getattr(get_settings(), "nexa_auto_approve_owner", True)) and is_privileged_owner_for_web_mutations(
        db, uid
    ):
        stamped_try = stamp_host_payload(dict(inferred))
        safe_now = _validate_enqueue_payload(stamped_try)
        if safe_now:

            class _UidJob:
                user_id = uid
                payload_json: dict[str, Any] = {}

            try:
                text_out = execute_payload(safe_now, db=db, job=_UidJob())
            except ValueError as exc:
                return NextActionApplicationResult(
                    f"I couldn’t run that on the host: {exc}"[:4000],
                    t0,
                    False,
                    True,
                    None,
                )
            reply = (text_out or "").strip()[:12000] or "(no output)"
            return NextActionApplicationResult(
                reply,
                t0,
                False,
                True,
                None,
                intent_override="command_completed",
            )

    _set_host_pending(cctx, inferred, title)
    db.add(cctx)
    db.commit()
    return NextActionApplicationResult(
        format_host_confirmation(inferred, title),
        t0,
        False,
        True,
        None,
    )


def drain_host_executor_web_notifications(
    db: Session, app_user_id: str, web_session_id: str
) -> tuple[str | None, list[dict[str, str]]]:
    """
    Surface completed host-executor jobs that were queued from this web session (once).

    Returns (assistant_prefix_text_or_none, muted_system_event_rows).
    """
    wid = (web_session_id or "default").strip()[:64] or "default"
    job_svc = AgentJobService()
    jobs = job_svc.list_jobs(db, app_user_id, limit=40)
    notes: list[str] = []
    events: list[dict[str, str]] = []
    repo = job_svc.repo
    for job in jobs:
        if (job.worker_type or "") != "local_tool":
            continue
        if (job.command_type or "").lower() != "host-executor":
            continue
        if (job.status or "") not in {"completed", "failed"}:
            continue
        pl = dict(job.payload_json or {})
        origin = pl.get("chat_origin") if isinstance(pl.get("chat_origin"), dict) else {}
        if (origin.get("web_session_id") or "") != wid:
            continue
        if pl.get("web_chat_notified"):
            continue
        title = str(pl.get("chat_pending_title") or job.title or "Host action")
        ok = (job.status or "") == "completed"
        notes.append(
            format_host_completion_message(
                job_id=job.id,
                title=title,
                success=ok,
                body=(job.result or "") if ok else None,
                err=(job.error_message or "") if not ok else None,
            )
        )
        events.append(
            {
                "kind": "local_action_muted",
                "text": completion_system_event_text(title, ok),
            }
        )
        pl["web_chat_notified"] = True
        repo.update(db, job, payload_json=pl)
    if not notes:
        return None, []
    return "\n\n---\n\n".join(notes), events


def try_apply_host_executor_turn(
    db: Session,
    cctx: ConversationContext,
    user_text: str,
    *,
    web_session_id: str | None = None,
):
    """
    Returns a NextActionApplicationResult when this turn is fully handled (confirm, queue, or decline).
    Returns None to continue normal co-pilot / LLM pipeline.
    """
    from app.services.next_action_apply import NextActionApplicationResult

    t0 = (user_text or "").strip()
    if not t0:
        return None

    sg0 = _secret_guard_reply_if_needed(t0)
    if sg0 is not None:
        return sg0

    if custom_agent_message_blocks_folder_heuristics(t0) or _agent_team_chat_blocks_folder_heuristics(
        t0
    ):
        return None

    raw_b = getattr(cctx, "blocked_host_executor_json", None)
    if (raw_b or "").strip():
        try:
            blocked = json.loads(raw_b)
        except (json.JSONDecodeError, TypeError, ValueError):
            blocked = None
        if isinstance(blocked, dict):
            uid_b = (cctx.user_id or "").strip()
            payload_b = blocked.get("payload")
            title_b = str(blocked.get("title") or "").strip()
            pid_b = blocked.get("permission_id")
            if isinstance(payload_b, dict) and title_b:
                from app.services.access_permissions import permission_denied_fallback_message

                if _declines_host_executor(t0) or (
                    re.match(r"(?i)^cancel\b", (user_text or "").strip()) is not None
                ):
                    cctx.blocked_host_executor_json = None
                    db.add(cctx)
                    db.commit()
                    return NextActionApplicationResult(
                        "Okay — I cancelled that permission request.",
                        t0,
                        False,
                        True,
                        None,
                    )

                ok_resume, _err_resume = precheck_host_executor_permissions(db, uid_b, payload_b)
                if ok_resume:
                    cctx.blocked_host_executor_json = None
                    _set_host_pending(cctx, payload_b, title_b)
                    db.add(cctx)
                    db.commit()
                    return NextActionApplicationResult(
                        format_host_confirmation(payload_b, title_b),
                        t0,
                        False,
                        True,
                        None,
                    )

                if is_permission_row_denied(db, int(pid_b) if pid_b is not None else None):
                    cctx.blocked_host_executor_json = None
                    db.add(cctx)
                    db.commit()
                    return NextActionApplicationResult(
                        permission_denied_fallback_message(),
                        t0,
                        False,
                        True,
                        None,
                    )

                if _confirms_host_executor(t0):
                    return NextActionApplicationResult(
                        still_waiting_permission_message(),
                        t0,
                        False,
                        True,
                        None,
                    )

                base_b = active_project_relative_base(db, uid_b, cctx)
                inf_r = infer_host_executor_action(t0)
                if not inf_r:
                    lf_r = infer_local_file_request(t0, default_relative_base=base_b)
                    if lf_r.matched and lf_r.error_message:
                        return NextActionApplicationResult(
                            lf_r.error_message,
                            t0,
                            False,
                            True,
                            None,
                        )
                    if lf_r.matched and lf_r.clarification_message:
                        return NextActionApplicationResult(
                            lf_r.clarification_message,
                            t0,
                            False,
                            True,
                            None,
                        )
                    if lf_r.matched and lf_r.path_resolution_failed:
                        return NextActionApplicationResult(
                            "That folder isn’t under Nexa’s configured host work root (`HOST_EXECUTOR_WORK_ROOT`). "
                            "Adjust the work root to include it, register it with `/workspace add`, then ask again.",
                            t0,
                            False,
                            True,
                            None,
                        )
                    if lf_r.matched and lf_r.payload:
                        inf_r = lf_r.payload
                if inf_r and base_b != ".":
                    inf_r = merge_payload_with_project_base(inf_r, base_b)
                if inf_r:
                    same = json.dumps(
                        _host_payload_semantic_for_compare(inf_r),
                        sort_keys=True,
                        default=str,
                    ) == json.dumps(
                        _host_payload_semantic_for_compare(payload_b),
                        sort_keys=True,
                        default=str,
                    )
                    if same:
                        sc, tg, rk = permission_fields_for_enqueue_payload(payload_b)
                        ws_dup = (
                            web_session_id or getattr(cctx, "session_id", None) or "default"
                        ).strip()[:64]
                        msg_dup, row_dup, _reused = request_permission_from_chat(
                            db,
                            uid_b,
                            scope=sc,
                            target=tg,
                            risk_level=rk,
                            reason=derive_permission_reason(
                                sc, reason_override=reason_for_host_payload(payload_b)
                            ),
                            metadata={
                                "host_action": str(payload_b.get("host_action") or "")[:64],
                            },
                            pending_payload=payload_b,
                            pending_title=title_b,
                            web_session_id=ws_dup,
                        )
                        rsn = derive_permission_reason(
                            sc, reason_override=reason_for_host_payload(payload_b)
                        )
                        perm_req = permission_required_payload(
                            permission_request_id=row_dup.id,
                            scope=sc,
                            target=tg,
                            reason=rsn,
                            risk_level=rk,
                            message=card_message_for_host_payload(payload_b),
                        )
                        return NextActionApplicationResult(
                            msg_dup,
                            t0,
                            False,
                            True,
                            None,
                            permission_required=perm_req,
                        )

                # Pending permission — do not fall through to LLM with unrelated user text.
                sc2, tg2, rk2 = permission_fields_for_enqueue_payload(payload_b)
                rsn2 = derive_permission_reason(
                    sc2, reason_override=reason_for_host_payload(payload_b)
                )
                try:
                    prid = int(pid_b) if pid_b is not None else None
                except (TypeError, ValueError):
                    prid = None
                if prid is not None:
                    perm_blk = permission_required_payload(
                        permission_request_id=prid,
                        scope=sc2,
                        target=tg2,
                        reason=rsn2,
                        risk_level=rk2,
                        message=card_message_for_host_payload(payload_b),
                    )
                    return NextActionApplicationResult(
                        still_waiting_permission_message(),
                        t0,
                        False,
                        True,
                        None,
                        permission_required=perm_blk,
                    )
                return None

            cctx.blocked_host_executor_json = None
            db.add(cctx)
            db.commit()

    parsed = _parse_pending_host_executor(cctx.next_action_pending_inject_json)
    if parsed:
        payload0, title0 = parsed
        pend_raw = cctx.next_action_pending_inject_json
        if is_pending_inject_expired(pend_raw):
            cctx.next_action_pending_inject_json = None
            db.add(cctx)
            db.commit()
            return NextActionApplicationResult(
                (
                    "That confirmation expired. Ask again if you still want something run on your "
                    "machine via Nexa."
                ),
                t0,
                False,
                True,
                None,
            )

        if _declines_host_executor(t0):
            cctx.next_action_pending_inject_json = None
            db.add(cctx)
            db.commit()
            return NextActionApplicationResult(
                "Okay — I won’t queue anything on your machine.",
                t0,
                False,
                True,
                None,
            )

        if _confirms_host_executor(t0):
            if not get_settings().nexa_host_executor_enabled:
                return NextActionApplicationResult(
                    "Host execution is disabled (`NEXA_HOST_EXECUTOR_ENABLED`). "
                    "Enable it on the API host if you want queueing from chat.",
                    t0,
                    False,
                    True,
                    None,
                )
            safe_pl = _validate_enqueue_payload(payload0)
            if not safe_pl:
                cctx.next_action_pending_inject_json = None
                db.add(cctx)
                db.commit()
                return NextActionApplicationResult(
                    "I couldn’t validate that host action anymore. Ask again with a supported request.",
                    t0,
                    False,
                    True,
                    None,
                )
            uid = (cctx.user_id or "").strip()
            wid = (web_session_id or getattr(cctx, "session_id", None) or "default").strip()[
                :64
            ] or "default"
            job = enqueue_host_job_from_validated_payload(
                db,
                uid,
                safe_pl=safe_pl,
                title=title0,
                web_session_id=wid,
            )
            cctx.next_action_pending_inject_json = None
            db.add(cctx)
            db.commit()
            logger.info(
                "host_executor chat queued job id=%s user=%s action=%s",
                job.id,
                uid,
                safe_pl.get("host_action"),
            )
            q_msg = format_queued_ack(title0, job.id)
            sys_evt = (
                (
                    "local_action",
                    f"Local action queued — Job #{job.id} ({title0}). Approve below or ask for recent jobs in chat.",
                ),
            )
            return NextActionApplicationResult(
                q_msg,
                t0,
                False,
                True,
                None,
                related_job_ids=(job.id,),
                pending_system_events=sys_evt,
            )

        return None

    if _legacy_command_pending(cctx.next_action_pending_inject_json):
        return None

    if not get_settings().nexa_host_executor_enabled:
        return None

    # Deterministic infer + permission is enforced in apply_next_action_to_user_text (pre-LLM).
    return None
