"""Persist per-user Mission Control UI dismissals (attention rows without durable rows)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from app.services.agent_runtime.paths import memory_dir
from app.services.agent_runtime.workspace_files import atomic_write_json, read_json_file

_LOCK = threading.Lock()
_FILENAME = "mission_control_ui_state.json"


def _path() -> Path:
    memory_dir().mkdir(parents=True, exist_ok=True)
    return memory_dir() / _FILENAME


def _load_all() -> dict[str, Any]:
    return read_json_file(_path(), {"version": 1, "users": {}})


def _save_all(data: dict[str, Any]) -> None:
    atomic_write_json(_path(), data)


def dismiss_attention_item(user_id: str, item_id: str) -> None:
    uid = (user_id or "").strip()[:64]
    iid = (item_id or "").strip()[:256]
    if not uid or not iid:
        return
    with _LOCK:
        root = _load_all()
        users: dict[str, Any] = root.setdefault("users", {})
        bucket: dict[str, Any] = users.setdefault(uid, {})
        dismissed: list[str] = list(bucket.get("dismissed_attention_ids") or [])
        if iid not in dismissed:
            dismissed.append(iid)
            bucket["dismissed_attention_ids"] = dismissed[-500:]
        users[uid] = bucket
        _save_all(root)


def clear_attention_dismissals(user_id: str) -> None:
    uid = (user_id or "").strip()[:64]
    if not uid:
        return
    with _LOCK:
        root = _load_all()
        users = root.setdefault("users", {})
        if uid in users and isinstance(users[uid], dict):
            users[uid]["dismissed_attention_ids"] = []
        _save_all(root)


def is_attention_dismissed(user_id: str, item_id: str) -> bool:
    uid = (user_id or "").strip()[:64]
    iid = (item_id or "").strip()[:256]
    if not uid or not iid:
        return False
    root = _load_all()
    users = root.get("users") or {}
    bucket = users.get(uid) or {}
    dismissed = bucket.get("dismissed_attention_ids") or []
    return iid in set(dismissed)


def dismissed_attention_ids(user_id: str) -> frozenset[str]:
    uid = (user_id or "").strip()[:64]
    if not uid:
        return frozenset()
    root = _load_all()
    users = root.get("users") or {}
    bucket = users.get(uid) or {}
    return frozenset(str(x) for x in (bucket.get("dismissed_attention_ids") or []) if x)
