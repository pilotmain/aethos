"""Phase 44–45 — rank memory for task context; adaptive weights from feedback (Phase 45D)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.memory.memory_index import MemoryIndex
from app.services.memory.memory_store import MemoryStore
from app.services.tasks.unified_task import NexaTask


def _weights_path(user_id: str) -> Path:
    return MemoryStore().user_dir(user_id) / "memory_weights.json"


def load_memory_weights(user_id: str) -> dict[str, float]:
    p = _weights_path(user_id)
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def update_memory_weights(user_id: str, feedback: dict[str, Any]) -> None:
    """
    Boost ids that led to success; decay on failure. Stored next to the memory index (JSON file).
    """
    weights = load_memory_weights(user_id)
    success = bool(feedback.get("success"))
    for eid in feedback.get("entry_ids") or []:
        if not eid:
            continue
        key = str(eid)
        cur = float(weights.get(key, 1.0))
        if success:
            weights[key] = min(2.0, cur + 0.08)
        else:
            weights[key] = max(0.25, cur - 0.06)
    p = _weights_path(user_id)
    p.write_text(json.dumps(weights, ensure_ascii=False, indent=0), encoding="utf-8")


def _weighted_rerank(entries: list[dict[str, Any]], weights: dict[str, float]) -> list[dict[str, Any]]:
    if not entries or not weights:
        return entries
    scored: list[tuple[float, dict[str, Any]]] = []
    for i, e in enumerate(entries):
        eid = str(e.get("id") or "")
        w = float(weights.get(eid, 1.0))
        scored.append((w / (i + 1), e))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored]


def build_intelligent_context(
    task: NexaTask,
    *,
    user_id: str,
    max_chars: int = 2800,
    memory_fn: MemoryIndex | None = None,
) -> dict[str, Any]:
    """
    Select memory entries relevant to the task (semantic ranking when query present).
    Applies Phase 45D weighting so useful entries stay prominent.
    """
    mi = memory_fn or MemoryIndex()
    q = (task.input or "").strip() or str(task.context.get("summary") or "").strip()
    ranked = mi.semantic_search(user_id, q, limit=12) if q else []
    ranked = _weighted_rerank(ranked, load_memory_weights(user_id))
    lines: list[str] = []
    for e in ranked[:8]:
        title = str(e.get("title") or "")
        preview = str(e.get("preview") or "")[:420]
        lines.append(f"- {title}: {preview}")
    blob = "\n".join(lines)[:max_chars]
    return {
        "task_type": task.type,
        "query_used": q[:800],
        "selected_entry_ids": [str(e.get("id") or "") for e in ranked[:12]],
        "prompt_injection": blob,
        "ranked_entries_json": json.dumps(ranked[:12], default=str)[:12_000],
    }


__all__ = ["build_intelligent_context", "load_memory_weights", "update_memory_weights"]
