"""Host allowlist / deny / open modes for outbound HTTP."""

from __future__ import annotations

import ipaddress
from collections import deque
from typing import Any
from urllib.parse import urlparse

from app.core.config import get_settings

_LOCAL_LABELS = frozenset({"localhost", "127.0.0.1", "::1"})
_EGRESS_HISTORY: deque[dict[str, Any]] = deque(maxlen=500)


def _normalize_host(raw: str | None) -> str:
    h = (raw or "").strip().lower()
    if h.endswith("."):
        h = h[:-1]
    return h


def _parse_allowed_hosts_csv(csv: str) -> frozenset[str]:
    out: set[str] = set()
    for part in (csv or "").split(","):
        p = _normalize_host(part)
        if p:
            out.add(p)
    return frozenset(out)


def _is_local_host(hostname: str) -> bool:
    h = _normalize_host(hostname)
    if h in _LOCAL_LABELS:
        return True
    try:
        ipaddress.ip_address(h)
        if h in ("127.0.0.1", "::1"):
            return True
    except ValueError:
        pass
    return False


def _hostname_from_url(url: str) -> str:
    try:
        return _normalize_host(urlparse(url).hostname)
    except Exception:  # noqa: BLE001
        return ""


def is_egress_allowed(url: str, purpose: str, user_id: str | None) -> bool:
    """
    Returns whether an outbound request to ``url`` is permitted.

    Modes (``NEXA_NETWORK_EGRESS_MODE``):
    - ``open``: allow all destinations.
    - ``deny``: only loopback / local hosts.
    - ``allowlist``: hosts in ``NEXA_NETWORK_ALLOWED_HOSTS`` plus local hosts.
    """
    s = get_settings()
    mode = (getattr(s, "nexa_network_egress_mode", None) or "allowlist").strip().lower()
    hn = _hostname_from_url(url)
    if not hn:
        return False
    if mode in ("open", "allow_all", "all"):
        return True
    if mode in ("deny", "deny_all", "localhost_only"):
        return _is_local_host(hn)
    allowed = _parse_allowed_hosts_csv(getattr(s, "nexa_network_allowed_hosts", "") or "")
    if _is_local_host(hn):
        return True
    return hn in allowed


def record_egress_attempt(
    *,
    url: str,
    purpose: str,
    user_id: str | None,
    allowed: bool,
    detail: str | None = None,
) -> None:
    """Append-only ring buffer for diagnostics (no secrets)."""
    _EGRESS_HISTORY.appendleft(
        {
            "url_host": _hostname_from_url(url),
            "purpose": (purpose or "")[:120],
            "user_id": (user_id or "")[:64],
            "allowed": bool(allowed),
            "detail": (detail or "")[:200],
        }
    )


def recent_egress_attempts(*, limit: int = 20) -> list[dict[str, Any]]:
    return list(_EGRESS_HISTORY)[: max(1, min(limit, 100))]


def provider_canonical_probe_url(provider: str) -> str | None:
    """Synthetic URL used only for hostname extraction in egress checks."""
    p = (provider or "").strip().lower()
    if p in ("local_stub",):
        return "http://127.0.0.1/"
    if p == "ollama":
        s = get_settings()
        base = (getattr(s, "nexa_ollama_base_url", None) or "http://127.0.0.1:11434").strip()
        if not base.startswith("http"):
            base = f"http://{base}"
        return base
    if p == "anthropic":
        return "https://api.anthropic.com/"
    if p == "openai":
        return "https://api.openai.com/"
    if p == "deepseek":
        return "https://api.deepseek.com/"
    if p == "openrouter":
        return "https://openrouter.ai/"
    if p in ("google", "gemini"):
        return "https://generativelanguage.googleapis.com/"
    return None


def assert_provider_egress_allowed(provider: str, user_id: str | None) -> str | None:
    """
    Returns ``None`` if allowed, otherwise a short machine-readable block reason.
    """
    url = provider_canonical_probe_url(provider)
    if url is None:
        return None
    ok = is_egress_allowed(url, purpose="provider_gateway", user_id=user_id)
    record_egress_attempt(
        url=url,
        purpose="provider_gateway",
        user_id=user_id,
        allowed=ok,
        detail=provider,
    )
    if ok:
        return None
    return "network_egress_blocked"


__all__ = [
    "assert_provider_egress_allowed",
    "is_egress_allowed",
    "provider_canonical_probe_url",
    "recent_egress_attempts",
    "record_egress_attempt",
]
