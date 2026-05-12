# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Create assignments and dispatch (sequential or bounded parallel). Phase 16a."""

from __future__ import annotations

import concurrent.futures
import logging
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.agent_team.service import (
    create_assignment,
    dispatch_assignment,
    get_or_create_default_organization,
)
from app.services.orchestration.policy import load_policy, validate_handles

logger = logging.getLogger(__name__)


def _spawn_group_id() -> str:
    return uuid.uuid4().hex[:24]


def run_delegation(
    db: Session,
    user_id: str,
    agents: list[str],
    goal: str,
    *,
    parallel: bool = False,
    channel: str = "web",
    web_session_id: str | None = None,
) -> dict[str, Any]:
    """
    Create one assignment per agent, then dispatch.

    Parallel dispatches use a thread pool; each thread opens its own DB session (SQLite-safe).
    """
    uid = (user_id or "").strip()[:64]
    policy = load_policy()
    norm, err = validate_handles(agents, policy=policy)
    if err:
        return {"ok": False, "error": err, "results": []}

    goal_text = (goal or "").strip()[:12_000]
    spawn_gid = _spawn_group_id()
    org = get_or_create_default_organization(db, uid)
    org_id = org.id

    require = bool(getattr(get_settings(), "nexa_orch_require_approval", False))
    initial_status = "waiting_approval" if require else "queued"

    assignment_ids: list[int] = []
    titlesuffix = goal_text[:120].replace("\n", " ")

    for h in norm:
        title = f"[Orchestration] → @{h}: {titlesuffix}"
        try:
            row = create_assignment(
                db,
                user_id=uid,
                assigned_to_handle=h,
                title=title[:500],
                description=goal_text[:20_000],
                organization_id=org_id,
                assigned_by_handle="orchestrator",
                priority="normal",
                input_json={
                    "user_message": goal_text,
                    "spawn_group_id": spawn_gid,
                    "orchestration": True,
                },
                channel=channel[:32],
                web_session_id=web_session_id,
                skip_duplicate_check=True,
                initial_status=initial_status,
            )
            assignment_ids.append(row.id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("orchestration create_assignment failed")
            return {"ok": False, "error": str(exc)[:2000], "results": [], "spawn_group_id": spawn_gid}

    logger.info(
        "orchestration delegate created assignments=%s parallel=%s spawn_group_id=%s",
        len(assignment_ids),
        parallel,
        spawn_gid,
        extra={
            "nexa_event": "orchestration_delegate",
            "parallel": parallel,
            "agent_count": len(assignment_ids),
            "spawn_group_id": spawn_gid,
            "requires_approval": require,
        },
    )

    if require:
        return {
            "ok": True,
            "spawn_group_id": spawn_gid,
            "assignment_ids": assignment_ids,
            "results": [
                {
                    "ok": True,
                    "assignment_id": aid,
                    "skipped_dispatch": True,
                    "reason": "waiting_approval",
                }
                for aid in assignment_ids
            ],
            "message": "Assignments queued for approval (NEXA_ORCH_REQUIRE_APPROVAL).",
        }

    timeout_s = max(policy.timeout_ms / 1000.0, 5.0)
    max_workers = min(len(assignment_ids), policy.max_parallel) if parallel else 1

    if parallel and max_workers > 1:

        def _run_one(aid: int) -> dict[str, Any]:
            from app.core.db import SessionLocal
            from app.services.agent_team.service import dispatch_assignment as disp

            t0 = time.perf_counter()
            with SessionLocal() as sdb:
                out = disp(sdb, assignment_id=aid, user_id=uid)
            ms = (time.perf_counter() - t0) * 1000.0
            if isinstance(out, dict):
                out = {**out, "duration_ms": round(ms, 2)}
            return out if isinstance(out, dict) else {"ok": False, "error": "invalid dispatch response"}

        results: list[dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futs = [pool.submit(_run_one, aid) for aid in assignment_ids]
            for fut, aid in zip(futs, assignment_ids, strict=True):
                try:
                    results.append(fut.result(timeout=timeout_s))
                except Exception as exc:  # noqa: BLE001
                    results.append({"ok": False, "assignment_id": aid, "error": str(exc)[:2000]})
        ok = all(r.get("ok") for r in results if isinstance(r, dict))
        return {
            "ok": ok,
            "spawn_group_id": spawn_gid,
            "assignment_ids": assignment_ids,
            "results": results,
            "parallel": True,
        }

    results_seq: list[dict[str, Any]] = []
    for aid in assignment_ids:
        t0 = time.perf_counter()
        out = dispatch_assignment(db, assignment_id=aid, user_id=uid)
        ms = (time.perf_counter() - t0) * 1000.0
        if isinstance(out, dict):
            out = {**out, "duration_ms": round(ms, 2)}
        results_seq.append(out if isinstance(out, dict) else {"ok": False, "error": "dispatch failed"})
    ok_all = all(r.get("ok") for r in results_seq if isinstance(r, dict))
    return {
        "ok": ok_all,
        "spawn_group_id": spawn_gid,
        "assignment_ids": assignment_ids,
        "results": results_seq,
        "parallel": False,
    }


def format_delegation_reply(payload: dict[str, Any]) -> str:
    """User-visible summary for gateway chat."""
    if not payload.get("ok") and payload.get("error"):
        return f"Delegation failed: {payload.get('error')}"

    if payload.get("message"):
        ids = payload.get("assignment_ids") or []
        return f"{payload['message']}\nIDs: {', '.join(str(i) for i in ids)}"

    parts: list[str] = []
    for i, r in enumerate(payload.get("results") or [], start=1):
        if not isinstance(r, dict):
            continue
        aid = r.get("assignment_id")
        if r.get("ok"):
            out = r.get("output") or {}
            text = ""
            if isinstance(out, dict):
                text = str(out.get("text") or "")[:2500]
            parts.append(f"**Delegation {i}** (assignment #{aid})\n{text or '(done)'}")
        else:
            parts.append(f"**Delegation {i}** ❌ {r.get('error', 'failed')[:1200]}")
    return "\n\n---\n\n".join(parts) if parts else "Delegation finished."


__all__ = ["format_delegation_reply", "run_delegation"]
