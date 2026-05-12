# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Nexa Gateway — central runtime layer for sessions, routing, agents, tools, channels,
privacy filtering, and Mission Control (incremental rollout).

All channels should converge on ``gateway.runtime.NexaGateway`` — implementation grows phase-by-phase.
"""

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway

__all__ = ["GatewayContext", "NexaGateway"]
