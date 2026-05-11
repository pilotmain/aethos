"""Optional ``aethos_pro`` extensions via ``aethos-core`` :class:`~aethos_core.plugin_manager.PluginManager`.

Does **not** replace in-repo components such as :class:`~app.services.inter_agent_coordinator.AgentNegotiator`
or ``app.services.self_healing`` — those remain the default integration paths. Use these accessors when a
commercial ``aethos-pro`` wheel is installed and ``AETHOS_PRO_ENABLED`` is set.
"""

from __future__ import annotations

from typing import Any


def resolve_optional_pro_classes() -> dict[str, type | None]:
    """
    Best-effort resolve classes from installed ``aethos_pro.*`` modules.

    Returns keys ``GoalPlanner``, ``SelfHealingEngine``, ``AgentNegotiator`` (Pro stubs), or ``None``.
    """
    try:
        from aethos_core.plugin_manager import PluginManager
    except ImportError:
        return {
            "GoalPlanner": None,
            "SelfHealingEngine": None,
            "AgentNegotiator": None,
        }

    out: dict[str, type | None] = {
        "GoalPlanner": None,
        "SelfHealingEngine": None,
        "AgentNegotiator": None,
    }
    gp = PluginManager.load_proprietary("goal_planner", fallback=None)
    if gp is not None:
        out["GoalPlanner"] = getattr(gp, "GoalPlanner", None)
    sh = PluginManager.load_proprietary("self_healing", fallback=None)
    if sh is not None:
        out["SelfHealingEngine"] = getattr(sh, "SelfHealingEngine", None)
    ng = PluginManager.load_proprietary("negotiation", fallback=None)
    if ng is not None:
        out["AgentNegotiator"] = getattr(ng, "AgentNegotiator", None)
    return out


def optional_goal_planner_class() -> type | None:
    return resolve_optional_pro_classes()["GoalPlanner"]


def optional_self_healing_engine_pro_class() -> type | None:
    """Pro-package ``SelfHealingEngine`` (distinct from in-repo genesis loop helpers)."""
    return resolve_optional_pro_classes()["SelfHealingEngine"]


def optional_agent_negotiator_pro_class() -> type | None:
    """Pro-package ``AgentNegotiator`` (distinct from :mod:`app.services.inter_agent_coordinator`)."""
    return resolve_optional_pro_classes()["AgentNegotiator"]


__all__ = [
    "resolve_optional_pro_classes",
    "optional_goal_planner_class",
    "optional_self_healing_engine_pro_class",
    "optional_agent_negotiator_pro_class",
]
