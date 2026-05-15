# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deployment-scoped artifact index (mirrors plan step outputs)."""

from __future__ import annotations

from typing import Any


def artifacts_from_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in plan.get("steps") or []:
        if not isinstance(s, dict):
            continue
        if str(s.get("type") or "") != "deploy":
            continue
        sid = str(s.get("step_id") or "")
        res = s.get("result") if isinstance(s.get("result"), dict) else {}
        out.append({"step_id": sid, "kind": "deploy", "tool": res.get("tool"), "ok": res.get("ok")})
        for o in s.get("outputs") or []:
            if isinstance(o, dict):
                out.append({"step_id": sid, "kind": "output", **o})
    return out
