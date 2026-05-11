"""Lightweight in-process traces/metrics/alerts (optional; gateway NL hooks)."""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, TypeVar

from app.core.config import get_settings

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class Trace:
    id: str
    operation: str
    start_time: datetime
    end_time: datetime | None = None
    status: str = "running"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Metric:
    name: str
    value: float
    unit: str
    timestamp: datetime
    labels: dict[str, Any] = field(default_factory=dict)


class ObservabilityService:
    """Bounded in-memory store (single-process dev aid)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._traces: dict[str, Trace] = {}
        self._metrics: deque[Metric] = deque(maxlen=5000)
        self._alerts: deque[dict[str, Any]] = deque(maxlen=500)

    def _trim_traces(self) -> None:
        s = get_settings()
        if not bool(getattr(s, "nexa_observability_enabled", False)):
            return
        hours = max(1, int(getattr(s, "nexa_trace_retention_hours", 24) or 24))
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        dead = [tid for tid, t in self._traces.items() if t.start_time.replace(tzinfo=UTC) < cutoff]
        for tid in dead:
            self._traces.pop(tid, None)

    def start_trace(self, operation: str, metadata: dict[str, Any] | None = None) -> str:
        if not bool(getattr(get_settings(), "nexa_observability_enabled", False)):
            return ""
        trace_id = str(uuid.uuid4())
        with self._lock:
            self._trim_traces()
            self._traces[trace_id] = Trace(
                id=trace_id,
                operation=operation,
                start_time=datetime.now(UTC),
                metadata=dict(metadata or {}),
            )
        return trace_id

    def end_trace(self, trace_id: str, status: str = "success") -> None:
        if not trace_id or not bool(getattr(get_settings(), "nexa_observability_enabled", False)):
            return
        with self._lock:
            t = self._traces.get(trace_id)
            if t:
                t.end_time = datetime.now(UTC)
                t.status = status

    def record_metric(self, name: str, value: float, unit: str = "count", labels: dict[str, Any] | None = None) -> None:
        if not bool(getattr(get_settings(), "nexa_observability_enabled", False)):
            return
        with self._lock:
            self._metrics.append(
                Metric(
                    name=name,
                    value=value,
                    unit=unit,
                    timestamp=datetime.now(UTC),
                    labels=dict(labels or {}),
                )
            )

    def send_alert(self, title: str, message: str, severity: str = "warning") -> None:
        if not bool(getattr(get_settings(), "nexa_observability_enabled", False)):
            return
        alert = {
            "title": title,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now(UTC).isoformat(),
            "resolved": False,
        }
        with self._lock:
            self._alerts.append(alert)
        ch = str(getattr(get_settings(), "nexa_alert_channel", "log") or "log").lower()
        if ch in ("log", "both"):
            logger.warning("observability.alert %s: %s — %s", severity, title, message)
        if ch in ("chat", "both"):
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_noop_chat_alert(alert))
            except RuntimeError:
                pass

    def list_recent_metrics(self, limit: int = 15) -> list[Metric]:
        with self._lock:
            return list(self._metrics)[-max(1, limit) :]

    def list_active_alerts(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = [a for a in self._alerts if not a.get("resolved")]
            return rows[-max(1, limit) :]

    def get_dashboard_markdown(self) -> str:
        with self._lock:
            active = [t for t in self._traces.values() if t.status == "running"]
            recent_m = list(self._metrics)[-10:]
            active_alerts = [a for a in self._alerts if not a.get("resolved")]
        lines = ["## System observability", ""]
        lines.append(f"### Active operations ({len(active)})")
        for t in active[:8]:
            lines.append(f"- {t.operation} (`{t.id[:8]}…`)")
        lines.append("")
        lines.append("### Recent metrics")
        if recent_m:
            for m in recent_m:
                lines.append(f"- **{m.name}**: {m.value} {m.unit}")
        else:
            lines.append("- _(none recorded)_")
        lines.append("")
        lines.append("### Alerts")
        if active_alerts:
            for a in active_alerts[-8:]:
                lines.append(f"- **{a.get('severity')}** {a.get('title')}: {a.get('message')}")
        else:
            lines.append("- _(none)_")
        return "\n".join(lines)


_obs_instance: ObservabilityService | None = None


def get_observability() -> ObservabilityService:
    """Return the process-wide :class:`ObservabilityService` singleton."""
    global _obs_instance
    if _obs_instance is None:
        _obs_instance = ObservabilityService()
    return _obs_instance


async def _noop_chat_alert(_alert: dict[str, Any]) -> None:
    """Placeholder for routing alerts into chat channels."""
    return


def trace_execution(func: F) -> F:
    """Decorator for async functions."""

    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        obs = get_observability()
        tid = obs.start_trace(func.__name__)
        try:
            result = await func(*args, **kwargs)
            obs.end_trace(tid, "success")
            return result
        except Exception as exc:
            obs.end_trace(tid, "failed")
            obs.send_alert(f"{func.__name__} failed", str(exc)[:500], "warning")
            raise

    return wrapper  # type: ignore[return-value]


# NL routing for gateway / early_nl guards. Order: narrow (alerts/metrics) before broad “show …”.
_OBSERVABILITY_REGEX: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^(?:show|display|view)\s+(?:me\s+)?alerts?\b", re.I), "alerts"),
    (re.compile(r"^(?:show|display|view)\s+(?:me\s+)?metrics?\b", re.I), "metrics"),
    (re.compile(r"^(?:list|see)\s+alerts?\b", re.I), "alerts"),
    (re.compile(r"^(?:show|display|view)\s+(?:me\s+)?(?:system\s+)?(?:status|health|dashboard)\b", re.I), "full"),
    (re.compile(r"(?:show|display|view)\s+(?:me\s+)?(?:system\s+)?(?:status|health|dashboard)", re.I), "full"),
    (re.compile(r"(?:what|how)\b.+\b(system|status|health)\b", re.I), "full"),
    (re.compile(r"^is\s+everything\s+ok\??$", re.I), "full"),
    (re.compile(r"^health\s+check\b", re.I), "full"),
    (re.compile(r"^(?:show\s+me\s+)?system\s+status\b", re.I), "full"),
]


def parse_observability_intent(text: str) -> str | None:
    """Return dashboard kind: full | alerts | metrics (does not depend on env flags)."""
    raw = (text or "").strip().splitlines()[0].strip()
    if not raw:
        return None
    low = raw.lower()
    if low in ("show alerts", "list alerts", "active alerts", "alerts"):
        return "alerts"
    if low in ("show metrics", "metrics", "recent metrics"):
        return "metrics"
    literal_full = (
        "show me system status",
        "system status",
        "system observability",
        "observability dashboard",
        "show observability",
        "what's happening",
        "whats happening",
    )
    if low in literal_full or any(low.startswith(p) for p in literal_full):
        return "full"
    for rx, kind in _OBSERVABILITY_REGEX:
        if rx.search(raw):
            return kind
    return None


__all__ = [
    "Metric",
    "ObservabilityService",
    "Trace",
    "get_observability",
    "parse_observability_intent",
    "trace_execution",
]
