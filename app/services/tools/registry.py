"""Tool registry — descriptors and routing hints for worker execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings


@dataclass
class ToolDescriptor:
    name: str
    description: str
    risk_level: str
    provider: str
    pii_policy: str
    enabled: bool = True


TOOLS: dict[str, ToolDescriptor] = {
    "research": ToolDescriptor(
        name="research",
        description="Generate research notes",
        risk_level="model",
        provider="local_stub",
        pii_policy="firewall_required",
    ),
    "analysis": ToolDescriptor(
        name="analysis",
        description="Analysis / forecasting",
        risk_level="model",
        provider="local_stub",
        pii_policy="firewall_required",
    ),
    "qa_review": ToolDescriptor(
        name="qa_review",
        description="QA / risk review",
        risk_level="model",
        provider="local_stub",
        pii_policy="firewall_required",
    ),
    "artifact_write": ToolDescriptor(
        name="artifact_write",
        description="Write workspace artifacts",
        risk_level="workspace",
        provider="local_stub",
        pii_policy="firewall_required",
        enabled=False,
    ),
    "heartbeat": ToolDescriptor(
        name="heartbeat",
        description="Liveness / noop",
        risk_level="low",
        provider="local_stub",
        pii_policy="firewall_required",
    ),
    "mission_update": ToolDescriptor(
        name="mission_update",
        description="Mission status updates",
        risk_level="low",
        provider="local_stub",
        pii_policy="firewall_required",
        enabled=False,
    ),
}


def select_tool_for_agent(agent: dict[str, Any]) -> str:
    h = str(agent.get("handle", "")).lower()
    if "research" in h or "researcher" in h:
        return "research"
    if "analyst" in h or "trader" in h:
        return "analysis"
    if h.startswith("qa") or "_qa" in h or h.endswith("_qa") or h == "qa":
        return "qa_review"

    blob = f"{h} {agent.get('role', '')} {agent.get('task', '')}".lower()
    if TOOLS.get("web_search") and ("web search" in blob or "search the web" in blob):
        return "web_search"
    # Prefer explicit analyst/forecast/review cues before generic task words ("researcher" contains "research").
    if any(k in blob for k in ("forecast", "market", " write forecast", "forecast ")):
        return "analysis"
    if any(k in blob for k in ("review", "risk", " qa:", "qa review")):
        return "qa_review"
    if any(k in blob for k in ("breakthrough", "robotics trends", "find robotics")):
        return "research"
    return "heartbeat"


def get_provider_for_tool(tool_name: str) -> str:
    td = TOOLS.get(tool_name)
    p = "local_stub"
    if td and td.enabled:
        p = td.provider
    elif td:
        p = td.provider
    s = get_settings()
    if getattr(s, "nexa_local_first", False) and p in ("openai", "anthropic"):
        return "local_stub"
    return p


def list_tools() -> dict[str, ToolDescriptor]:
    return dict(TOOLS)


def register_tool(descriptor: ToolDescriptor) -> None:
    """Merge or replace a tool descriptor (used by plugins at startup)."""
    TOOLS[descriptor.name] = descriptor


__all__ = [
    "ToolDescriptor",
    "TOOLS",
    "select_tool_for_agent",
    "get_provider_for_tool",
    "list_tools",
    "register_tool",
]
