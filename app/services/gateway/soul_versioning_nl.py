# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Natural-language soul history / rollback (gateway fast path)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.gateway.context import GatewayContext
from app.services.host_executor_intent import match_soul_versioning_intent
from app.services.memory_service import MemoryService


def try_soul_versioning_nl_turn(
    gctx: GatewayContext,
    raw: str,
    db: Session,
) -> dict[str, Any] | None:
    kind, m = match_soul_versioning_intent(raw)
    if not kind:
        return None

    from app.services.gateway.runtime import gateway_finalize_chat_reply

    uid = (gctx.user_id or "").strip()
    if not uid:
        text = "Set your user id first — soul history is per account."
        return {"mode": "chat", "text": gateway_finalize_chat_reply(text, source="soul_nl", user_text=raw), "intent": kind}

    ms = MemoryService()

    if kind == "soul_history":
        from app.services.soul_manager import get_user_soul_history

        versions = get_user_soul_history(uid)
        if not versions:
            body = "No soul history yet — snapshots are created whenever your soul text changes."
        else:
            body = "**Soul version history (newest first):**\n" + "\n".join(f"- `{v}`" for v in versions)
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(body, source="soul_nl", user_text=raw),
            "intent": "soul_history",
        }

    if kind == "soul_rollback" and m:
        ver = (m.group(1) or "").strip()
        from app.services.soul_manager import read_user_soul_version

        blob = read_user_soul_version(uid, ver)
        if blob is None:
            body = f"Version `{ver}` not found under your soul history."
        else:
            ms.update_soul_markdown(db, uid, blob, source="chat_rollback", record_history=True)
            db.commit()
            body = f"Restored soul to snapshot `{ver}`."
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(body, source="soul_nl", user_text=raw),
            "intent": "soul_rollback",
        }

    if kind == "soul_rollback_previous":
        from app.services.soul_manager import get_user_soul_history, read_user_soul_version

        hist = get_user_soul_history(uid, limit=1)
        if not hist:
            body = "Nothing to roll back — no prior soul snapshots for this account."
        else:
            ver = hist[0]
            blob = read_user_soul_version(uid, ver)
            if blob is None:
                body = f"Snapshot `{ver}` is missing on disk."
            else:
                ms.update_soul_markdown(db, uid, blob, source="chat_rollback_previous", record_history=True)
                db.commit()
                body = f"Restored soul to the previous saved version (`{ver}`)."
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(body, source="soul_nl", user_text=raw),
            "intent": "soul_rollback_previous",
        }

    if kind == "soul_undo":
        from app.services.soul_manager import get_user_soul_history, read_user_soul_version

        hist = get_user_soul_history(uid, limit=1)
        if not hist:
            body = "Nothing to undo — no prior soul snapshots for this account."
        else:
            ver = hist[0]
            blob = read_user_soul_version(uid, ver)
            if blob is None:
                body = f"Snapshot `{ver}` is missing on disk."
            else:
                ms.update_soul_markdown(db, uid, blob, source="chat_undo", record_history=True)
                db.commit()
                body = f"Undid the last soul change (restored snapshot `{ver}`)."
        return {
            "mode": "chat",
            "text": gateway_finalize_chat_reply(body, source="soul_nl", user_text=raw),
            "intent": "soul_undo",
        }

    return None


__all__ = ["try_soul_versioning_nl_turn"]
