"""Filesystem-backed memory documents per user (Markdown + JSON hybrid)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT, get_settings


def _user_segment(user_id: str) -> str:
    h = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:32]
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", user_id)[:40]
    return f"{safe}_{h}"


class MemoryStore:
    """One directory per user: entries index (JSONL) + one file per entry (md)."""

    def __init__(self, base_dir: Path | None = None) -> None:
        s = get_settings()
        root = base_dir
        if root is None:
            raw = (s.nexa_memory_dir or "").strip()
            root = Path(raw) if raw else (REPO_ROOT / "data" / "nexa_memory")
        self.base_dir = root

    def user_dir(self, user_id: str) -> Path:
        p = self.base_dir / _user_segment(user_id)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def index_path(self, user_id: str) -> Path:
        return self.user_dir(user_id) / "entries.jsonl"

    def append_entry(
        self,
        user_id: str,
        *,
        kind: str,
        title: str,
        body_md: str,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        eid = _new_id()
        ts = _utc_now_iso()
        rec = {
            "id": eid,
            "ts": ts,
            "type": kind,
            "title": (title or "")[:500],
            "meta": meta or {},
        }
        path = self.user_dir(user_id) / f"{eid}.md"
        front = json.dumps(rec, ensure_ascii=False, sort_keys=True)
        path.write_text(f"---\n{front}\n---\n\n{body_md.strip()}\n", encoding="utf-8")
        line = json.dumps({**rec, "preview": body_md.strip()[:280]}, ensure_ascii=False)
        with self.index_path(user_id).open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return rec

    def list_entries(self, user_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        idx = self.index_path(user_id)
        if not idx.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with idx.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows[-limit:]

    def remove_entry(self, user_id: str, entry_id: str) -> bool:
        """Remove one entry from the index and delete its markdown file (best-effort)."""
        tid = (entry_id or "").strip()
        if not tid:
            return False
        idx = self.index_path(user_id)
        if not idx.is_file():
            return False
        kept: list[str] = []
        removed = False
        with idx.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    kept.append(line)
                    continue
                if str(row.get("id") or "") == tid:
                    removed = True
                    continue
                kept.append(line)
        if not removed:
            return False
        idx.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        md = self.user_dir(user_id) / f"{tid}.md"
        try:
            md.unlink(missing_ok=True)
        except OSError:
            pass
        return True

    def read_document(self, user_id: str) -> dict[str, Any]:
        """Aggregate view for API: entries + concatenated markdown summaries."""
        entries = self.list_entries(user_id, limit=500)
        parts: list[str] = []
        for e in entries:
            tid = str(e.get("id") or "")
            if not tid:
                continue
            fp = self.user_dir(user_id) / f"{tid}.md"
            if fp.is_file():
                parts.append(fp.read_text(encoding="utf-8"))
        return {
            "format": "nexa_memory_v1",
            "entry_count": len(entries),
            "entries": entries,
            "full_markdown": "\n\n---\n\n".join(parts) if parts else "",
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_id() -> str:
    return hashlib.sha256(_utc_now_iso().encode()).hexdigest()[:16]


__all__ = ["MemoryStore"]
