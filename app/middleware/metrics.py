"""Count HTTP requests for Phase 11 metrics."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.services.metrics.runtime import record_http_request


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        record_http_request()
        start = time.perf_counter()
        response = await call_next(request)
        _ = time.perf_counter() - start
        return response
