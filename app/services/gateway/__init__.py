"""
Nexa Gateway — central runtime layer for sessions, routing, agents, tools, channels,
privacy filtering, and Mission Control (incremental rollout).

All channels should converge on ``gateway.runtime.NexaGateway`` — implementation grows phase-by-phase.
"""

from app.services.gateway.runtime import NexaGateway

__all__ = ["NexaGateway"]
