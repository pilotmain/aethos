"""Deterministic local provider — no external HTTP (Phase 4 default)."""

from __future__ import annotations

from typing import Any


def call_local_stub(payload: dict[str, Any]) -> dict[str, Any]:
    task = str(payload.get("task", "")).lower()
    inputs = payload.get("inputs", [])
    handle = str(payload.get("handle", "")).lower()
    agent_role = str(payload.get("agent", "")).lower().strip()

    def _is_research() -> bool:
        return handle.startswith("researcher") or agent_role == "researcher"

    def _is_analyst() -> bool:
        return handle.startswith("analyst") or agent_role == "analyst"

    def _is_qa() -> bool:
        return handle.startswith("qa") or agent_role == "qa" or agent_role.startswith("qa")

    if _is_research():
        return {
            "type": "research_notes",
            "items": [
                "Embodied AI",
                "Warehouse robotics",
                "Sim-to-real learning",
            ],
        }

    if _is_analyst():
        return {
            "type": "forecast",
            "text": f"Based on inputs: {inputs}, robotics adoption is accelerating.",
        }

    if _is_qa():
        return {
            "type": "qa_report",
            "text": f"Reviewing outputs: {inputs}, risks include scaling and cost.",
        }

    if "forecast" in task or "market" in task:
        return {
            "type": "forecast",
            "text": f"Based on inputs: {inputs}, robotics adoption is accelerating.",
        }

    if "review" in task or "risk" in task:
        return {
            "type": "qa_report",
            "text": f"Reviewing outputs: {inputs}, risks include scaling and cost.",
        }

    if "research" in task or "breakthrough" in task:
        return {
            "type": "research_notes",
            "items": [
                "Embodied AI",
                "Warehouse robotics",
                "Sim-to-real learning",
            ],
        }

    if payload.get("tool") in ("heartbeat", "mission_update"):
        return {"type": str(payload.get("tool")), "ok": True}

    if payload.get("tool") == "artifact_write":
        return {"type": "artifact_write", "path": "(stub)", "bytes": 0}

    return {"type": "generic", "inputs_seen": inputs}
