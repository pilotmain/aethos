"""Channel adapters — every inbound path fans into :class:`~app.services.gateway.runtime.NexaGateway`."""

from app.services.channels.router import route_inbound

__all__ = ["route_inbound"]
