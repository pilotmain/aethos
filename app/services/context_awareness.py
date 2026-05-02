"""Phase 50 — lightweight infra / stack hints from user text (no network I/O)."""

from __future__ import annotations

import re

# Order: longer phrases first where relevant.
_INFRA_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\boidc\b|open.?id\s+connect|oauth2?\b"), "OIDC/OAuth"),
    (re.compile(r"(?i)\beks\b|elastic\s+kubernetes|amazon\s+kubernetes"), "EKS/Kubernetes"),
    (re.compile(r"(?i)\bgke\b|google\s+kubernetes"), "GKE/Kubernetes"),
    (re.compile(r"(?i)\bkubernetes\b|\bk8s\b|\bhelm\b"), "Kubernetes"),
    (re.compile(r"(?i)\bdocker\b|dockerfile|docker\s+compose"), "Docker"),
    (re.compile(r"(?i)\bmongo(db)?\b"), "MongoDB"),
    (re.compile(r"(?i)\bpostgres(ql)?\b|\brds\b"), "Postgres"),
    (re.compile(r"(?i)\bredis\b|\belasticache\b"), "Redis"),
    (re.compile(r"(?i)\bkafka\b"), "Kafka"),
    (re.compile(r"(?i)\bgrpc\b"), "gRPC"),
    (re.compile(r"(?i)\bci/cd\b|github\s+actions|gitlab\s+ci|jenkins"), "CI/CD"),
    (re.compile(r"(?i)\bnginx\b|ingress\b|load\s+balancer"), "Ingress/LB"),
)

_STACK_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\btypescript\b|\btsx?\b|\.tsx\b"), "TypeScript"),
    (re.compile(r"(?i)\bpython\b|pytest\b|\.py\b|\bpip\b"), "Python"),
    (re.compile(r"(?i)\brust\b|cargo\b"), "Rust"),
    (re.compile(r"(?i)\bgo\b|\bgolang\b|go\.mod\b"), "Go"),
    (re.compile(r"(?i)\bjava\b|gradle\b|maven\b"), "JVM"),
    (re.compile(r"(?i)\breact\b|next\.js\b|vite\b|npm\b|pnpm\b|yarn\b"), "JS/React"),
    (re.compile(r"(?i)\bruby\b|rails\b|bundle\b"), "Ruby"),
)


def detect_infra_context(text: str) -> list[str]:
    """Return ordered unique infra labels matching ``text``."""
    t = text or ""
    seen: set[str] = set()
    out: list[str] = []
    for rx, label in _INFRA_PATTERNS:
        if rx.search(t) and label not in seen:
            seen.add(label)
            out.append(label)
    return out


def detect_stack_tags(text: str) -> list[str]:
    """Return ordered unique language/framework labels."""
    t = text or ""
    seen: set[str] = set()
    out: list[str] = []
    for rx, label in _STACK_PATTERNS:
        if rx.search(t) and label not in seen:
            seen.add(label)
            out.append(label)
    return out


__all__ = ["detect_infra_context", "detect_stack_tags"]
