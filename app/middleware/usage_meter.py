"""Count API calls for cloud-authenticated JWT users (metering)."""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.services.billing.usage_tracker import track_usage
from app.services.cloud_saas.jwt_tokens import decode_cloud_access_token_payload

logger = logging.getLogger(__name__)


class UsageMeterMiddleware(BaseHTTPMiddleware):
    """After the response, record one API request for valid ``aethos_cloud`` bearer JWTs."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        try:
            if not get_settings().aethos_cloud_enabled:
                return response
            path = request.url.path
            if "/billing/webhook" in path or path.endswith("/health") or path.startswith("/docs"):
                return response
            auth = request.headers.get("authorization") or ""
            if not auth.lower().startswith("bearer "):
                return response
            token = auth[7:].strip()
            if not token:
                return response
            try:
                payload = decode_cloud_access_token_payload(token)
            except Exception:
                return response
            if str(payload.get("typ") or "") != "aethos_cloud":
                return response
            user_id = str(payload.get("sub") or "").strip()
            if user_id:
                track_usage(user_id, "api_call", 1)
        except Exception as exc:
            logger.debug("usage meter skip: %s", exc)
        return response


__all__ = ["UsageMeterMiddleware"]
