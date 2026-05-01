"""User-scoped JSON skill definitions on disk (Phase 22)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT


def _user_dir(user_id: str) -> Path:
    h = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", user_id)[:32]
    d = REPO_ROOT / "data" / "nexa_skills" / f"{safe}_{h}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_skill_docs(user_id: str) -> list[dict[str, Any]]:
    base = _user_dir(user_id)
    out: list[dict[str, Any]] = []
    for p in sorted(base.glob("*.json")):
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                raw = dict(raw)
                raw["_file"] = p.name
                out.append(raw)
        except (OSError, json.JSONDecodeError):
            continue
    return out


def save_skill_doc(user_id: str, name: str, doc: dict[str, Any]) -> Path:
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", name).strip("._") or "skill"
    path = _user_dir(user_id) / f"{safe_name}.json"
    body = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(body + "\n", encoding="utf-8")
    return path


__all__ = ["list_skill_docs", "save_skill_doc"]
