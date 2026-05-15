# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""In-memory view of ``st[\"deployment_records\"]`` (persisted via runtime_state)."""

from __future__ import annotations

from typing import Any


def deployment_records(st: dict[str, Any]) -> dict[str, Any]:
    d = st.setdefault("deployment_records", {})
    if not isinstance(d, dict):
        st["deployment_records"] = {}
        return st["deployment_records"]
    return d


def get_deployment(st: dict[str, Any], deployment_id: str) -> dict[str, Any] | None:
    row = deployment_records(st).get(str(deployment_id))
    return row if isinstance(row, dict) else None


def upsert_deployment(st: dict[str, Any], deployment_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    rid = str(deployment_id)
    cur = dict(deployment_records(st).get(rid) or {})
    cur.update(patch)
    deployment_records(st)[rid] = cur
    return cur


def list_deployments_for_user(st: dict[str, Any], user_id: str) -> list[dict[str, Any]]:
    uid = str(user_id or "").strip()
    out: list[dict[str, Any]] = []
    for _did, row in deployment_records(st).items():
        if not isinstance(row, dict):
            continue
        if uid and str(row.get("user_id") or "") != uid:
            continue
        out.append(dict(row))
    out.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    return out
