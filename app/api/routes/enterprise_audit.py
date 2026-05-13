# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Read recent JSONL enterprise audit files (owner-gated, same spirit as /audit/export)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.routes.audit_export import _assert_exporter
from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.services.user_capabilities import is_privileged_owner_for_web_mutations

router = APIRouter(prefix="/enterprise-audit", tags=["enterprise-audit"])


def _assert_enterprise_audit_viewer(db: Session, app_user_id: str) -> None:
    if get_settings().nexa_governance_enabled:
        _assert_exporter(db, app_user_id)
        return
    if not is_privileged_owner_for_web_mutations(db, app_user_id):
        raise HTTPException(status_code=403, detail="owner_required")


@router.get("/recent")
def list_recent_jsonl(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=200, ge=1, le=5000),
) -> dict[str, Any]:
    _assert_enterprise_audit_viewer(db, app_user_id)
    s = get_settings()
    if not bool(getattr(s, "audit_enabled", True)):
        return {"ok": True, "enabled": False, "events": []}

    root = Path(((s.audit_dir or "").strip() or str(Path.home() / ".aethos" / "audit"))).expanduser()
    if not root.is_dir():
        return {"ok": True, "enabled": True, "events": [], "dir": str(root)}

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    files: list[Path] = []
    d = start
    while d <= end:
        p = root / f"{d.isoformat()}.jsonl"
        if p.is_file():
            files.append(p)
        d += timedelta(days=1)

    events: list[dict[str, Any]] = []
    for fp in reversed(files):
        try:
            lines = fp.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            if len(events) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if len(events) >= limit:
            break

    return {"ok": True, "enabled": True, "dir": str(root), "events": events[:limit]}


__all__ = ["router"]
