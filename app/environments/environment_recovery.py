# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Environment recovery markers after restart."""

from __future__ import annotations

from typing import Any

from app.environments.environment_registry import environments_map
from app.orchestration import orchestration_log
from app.runtime.runtime_state import utc_now_iso


def recover_environments_on_boot(st: dict[str, Any]) -> dict[str, Any]:
    n = 0
    for eid, row in list(environments_map(st).items()):
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "") not in ("deploying", "recovering", "degraded"):
            continue
        ts = utc_now_iso()
        row["status"] = "recovering"
        row["updated_at"] = ts
        row["recovery"] = {"boot": ts, "note": "process_restart"}
        orchestration_log.append_json_log("environments", "environment_recovering", environment_id=str(eid))
        n += 1
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["environment_recovery_boot_total"] = int(m.get("environment_recovery_boot_total") or 0) + n
    return {"environments_touched": n}
