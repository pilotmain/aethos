# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Early NL shortcuts for gateway (read file, owner-only batch / React) before host confirmation."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.services.batch_executor import create_batch_files, parse_batch_create_intent
from app.services.gateway.context import GatewayContext
from app.services.host_executor import read_workspace_text_file
from app.services.host_executor_intent import parse_read_intent
from app.services.react_app_builder import create_react_app, parse_react_app_intent
from app.services.user_capabilities import is_privileged_owner_for_web_mutations


def _workspace_root_for_nl() -> str:
    s = get_settings()
    raw = str(getattr(s, "nexa_command_work_root", "") or "").strip()
    if raw:
        return raw
    raw_h = str(getattr(s, "host_executor_work_root", "") or "").strip()
    return raw_h or str(REPO_ROOT)


def try_early_nl_host_actions(
    gctx: GatewayContext,
    raw_message: str,
    db: Session,
) -> dict[str, Any] | None:
    """
    Deterministic shortcuts that bypass generic chat.

    - Read file: any user (paths scoped under ``NEXA_COMMAND_WORK_ROOT``).
    - Batch create / React scaffold: privileged owners only when ``nexa_auto_approve_owner`` is true.
    """
    raw = (raw_message or "").strip()
    uid = (gctx.user_id or "").strip()
    if not raw or not uid:
        return None

    read_intent = parse_read_intent(raw)
    if read_intent:
        fp = str(read_intent.get("filepath") or "").strip()
        result = read_workspace_text_file(fp, uid)
        if result.get("success"):
            content = str(result.get("content") or "")
            preview = content[:24_000]
            path_disp = result.get("path") or fp
            size = result.get("size")
            return {
                "mode": "chat",
                "text": f"📄 **{path_disp}**\n\n```\n{preview}\n```\n\n📏 Size: {size} bytes",
                "intent": "file_read",
                "host_executor": True,
            }
        return {
            "mode": "chat",
            "text": f"❌ {result.get('error') or 'Read failed'}",
            "intent": "file_read_error",
            "host_executor": True,
        }

    settings = get_settings()
    auto_approve = bool(getattr(settings, "nexa_auto_approve_owner", True)) and bool(
        is_privileged_owner_for_web_mutations(db, uid)
    )
    if not auto_approve:
        return None

    root = _workspace_root_for_nl()

    batch_intent = parse_batch_create_intent(raw)
    if batch_intent:
        files = batch_intent.get("files") or []
        res = create_batch_files(files, root, uid)
        names = "\n".join(f"  - {f['filename']}" for f in res.get("files") or [])
        pname = str(batch_intent.get("project_name") or "project")
        return {
            "mode": "chat",
            "text": (
                f"✅ Created {res.get('count', 0)} files for {pname}\n\n📁 Files:\n{names}"
            ),
            "intent": "batch_completed",
            "host_executor": True,
        }

    react_intent = parse_react_app_intent(raw)
    if react_intent:
        app_name = str(react_intent.get("app_name") or "").strip()
        result = create_react_app(app_name, root, owner_user_id=uid)
        steps = result.get("steps") or []
        lines = "\n".join(
            f"  - {s.get('step')}: {'✓' if s.get('success') else '✗'}" for s in steps
        )
        if result.get("success"):
            return {
                "mode": "chat",
                "text": (
                    f"✅ React app '{app_name}' created and started!\n\n"
                    f"🌐 Open: {result.get('app_url')}\n\n"
                    f"📁 Location: {result.get('app_path')}\n\n"
                    f"📋 Steps:\n{lines}"
                ),
                "intent": "react_app_completed",
                "host_executor": True,
            }
        return {
            "mode": "chat",
            "text": (
                f"❌ React scaffold failed for '{app_name}'.\n\n📋 Steps:\n{lines}"
            ),
            "intent": "react_app_error",
            "host_executor": True,
        }

    return None
