# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""CRUD helpers for ``st[\"environments\"]``."""

from __future__ import annotations

import hashlib
from typing import Any, Iterator

from app.runtime.runtime_state import utc_now_iso


def environments_map(st: dict[str, Any]) -> dict[str, Any]:
    e = st.setdefault("environments", {})
    if not isinstance(e, dict):
        st["environments"] = {}
        return st["environments"]
    return e


def default_environment_id_for_user(st: dict[str, Any], user_id: str) -> str:
    uid = str(user_id or "default").strip() or "default"
    h = hashlib.sha256(uid.encode("utf-8")).hexdigest()[:10]
    eid = f"env_{h}"
    ensure_environment(st, eid, user_id=uid, name="default")
    return eid


def ensure_environment(
    st: dict[str, Any],
    environment_id: str,
    *,
    user_id: str = "",
    name: str | None = None,
) -> dict[str, Any]:
    eid = str(environment_id).strip()
    em = environments_map(st)
    ts = utc_now_iso()
    if eid not in em or not isinstance(em.get(eid), dict):
        em[eid] = {
            "environment_id": eid,
            "name": (name or eid)[:120],
            "status": "healthy",
            "created_at": ts,
            "updated_at": ts,
            "user_id": str(user_id or ""),
            "variables": {},
            "metrics": {"deployment_success": 0, "deployment_failure": 0, "recovery_count": 0},
        }
        try:
            from app.runtime.events.runtime_events import emit_runtime_event

            emit_runtime_event(
                st,
                "environment_created",
                environment_id=eid,
                user_id=str(user_id or ""),
                status="healthy",
            )
        except Exception:
            pass
        return em[eid]
    row = em[eid]
    row["updated_at"] = ts
    if user_id and not str(row.get("user_id") or ""):
        row["user_id"] = str(user_id)
    if name:
        row["name"] = str(name)[:120]
    return row


def get_environment(st: dict[str, Any], environment_id: str) -> dict[str, Any] | None:
    row = environments_map(st).get(str(environment_id))
    return row if isinstance(row, dict) else None


def list_environments_for_user(st: dict[str, Any], user_id: str) -> list[dict[str, Any]]:
    uid = str(user_id or "").strip()
    out: list[dict[str, Any]] = []
    for _eid, row in environments_map(st).items():
        if not isinstance(row, dict):
            continue
        if uid and str(row.get("user_id") or "") != uid:
            continue
        out.append(dict(row))
    out.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    return out


def iter_environments(st: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for _eid, row in environments_map(st).items():
        if isinstance(row, dict):
            yield row
