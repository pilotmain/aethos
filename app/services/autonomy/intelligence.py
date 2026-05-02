"""Phase 44 — rank memory for task context instead of dumping everything."""

from __future__ import annotations

import json
from typing import Any

from app.services.memory.memory_index import MemoryIndex
from app.services.tasks.unified_task import NexaTask


def build_intelligent_context(
    task: NexaTask,
    *,
    user_id: str,
    max_chars: int = 2800,
    memory_fn: MemoryIndex | None = None,
) -> dict[str, Any]:
    """
    Select memory entries relevant to the task (semantic ranking when query present).
    Returns a compact structure suitable for planners or gateway extras.
    """
    mi = memory_fn or MemoryIndex()
    q = (task.input or "").strip() or str(task.context.get("summary") or "").strip()
    ranked = mi.semantic_search(user_id, q, limit=10) if q else []
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


__all__ = ["build_intelligent_context"]
