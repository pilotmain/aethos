"""
Mandatory outbound HTTP wrapper — product code should not call httpx/raw sockets directly.

Invariant: any POST/PUT/PATCH (or GET with user/model-derived body) that sends user or model
content off-machine must either:

- pass through ``outbound_request_gate.gate_outbound_http_body`` when the body should be
  scanned for secrets, or
- live in this module behind an allowlisted provider/internal host with documented rationale
  (provider keys often false-positive the gate — see outbound_request_gate module doc).

- User-facing GET (public pages): ``web_access.fetch_url`` after ``enforcement_pipeline`` preflight.
- Provider APIs (Brave/Tavily/SerpAPI): allowlisted hosts only.
- Internal probes (robots.txt): ``internal_get`` — no user egress permission row.
- Telegram notifications: ``telegram_send_message_post`` runs the egress gate on JSON bodies.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.services.network_policy.policy import is_egress_allowed, record_egress_attempt

logger = logging.getLogger(__name__)

_PROVIDER_HOSTS = frozenset(
    {
        "api.search.brave.com",
        "api.tavily.com",
        "serpapi.com",
        "www.googleapis.com",
    }
)


def _hostname(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").strip().lower()
    except Exception:  # noqa: BLE001
        return ""


def provider_get(url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: float = 20.0) -> httpx.Response:
    hn = _hostname(url)
    if hn not in _PROVIDER_HOSTS:
        raise ValueError(f"provider GET host not allowlisted: {hn!r}")
    logger.info("safe_http_client provider_get host=%s", hn)
    with httpx.Client(timeout=timeout) as client:
        return client.get(url, params=params or {}, headers=headers or {})


def provider_post(url: str, *, json: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: float = 25.0) -> httpx.Response:
    hn = _hostname(url)
    ok = is_egress_allowed(url, purpose="provider_post", user_id=None)
    record_egress_attempt(url=url, purpose="provider_post", user_id=None, allowed=ok)
    if not ok:
        raise ValueError(f"egress policy blocked host {hn!r}")
    if hn not in _PROVIDER_HOSTS:
        raise ValueError(f"provider POST host not allowlisted: {hn!r}")
    logger.info("safe_http_client provider_post host=%s", hn)
    with httpx.Client(timeout=timeout) as client:
        return client.post(url, json=json or {}, headers=headers or {})


def internal_get(url: str, *, headers: dict[str, str] | None = None, timeout: float = 15.0, max_redirects: int = 5) -> httpx.Response:
    """Best-effort fetch for robots.txt and similar — no user egress permission."""
    logger.info("safe_http_client internal_get hint=%s", url[:120])
    s = get_settings()
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(timeout),
        verify=True,
        max_redirects=max_redirects,
    ) as client:
        return client.get(url, headers=headers or {}, follow_redirects=True)


def telegram_send_message_post(full_url: str, *, json_body: dict[str, Any], timeout: float = 20.0) -> httpx.Response:
    hn = _hostname(full_url)
    if hn != "api.telegram.org":
        raise ValueError("telegram outbound must target api.telegram.org")
    from app.services.outbound_request_gate import gate_outbound_http_body

    payload_txt = json.dumps(json_body, ensure_ascii=False)
    gate_outbound_http_body(
        payload_txt,
        url=full_url,
        method="POST",
        db=None,
        owner_user_id=None,
        instruction_source="telegram_notification",
    )
    with httpx.Client(timeout=timeout) as client:
        return client.post(full_url, json=json_body, timeout=timeout)
