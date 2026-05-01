"""Lightweight, deterministic project / env / service token extraction (no free-form shell)."""

from __future__ import annotations

import re
from typing import Any

# Normalized target environment labels used in payload
COMMON_ENVS: dict[str, str] = {
    "local": "local",
    "dev": "dev",
    "development": "dev",
    "staging": "staging",
    "stage": "staging",
    "stg": "staging",
    "prod": "production",
    "production": "production",
    "pro": "production",
}

_COMMON_SERVICE: frozenset[str] = frozenset(
    {"api", "bot", "worker", "db", "postgres", "redis", "app", "web", "all"}
)


def _norm(s: str) -> str:
    return s.strip().lower().rstrip(".,:;!?")


def _words(text: str) -> list[str]:
    t = re.sub(r"[@#]", " ", (text or "").lower())
    t = re.sub(r"[,]", " ", t)
    return [w for w in t.split() if w]


def parse_ops_project_scopes(
    text: str,
    *,
    known_project_keys: list[str],
) -> dict[str, Any]:
    """
    Scans word tokens for known project key, environment, and a single service (whitelisted name).
    """
    keys = {_norm(k) for k in known_project_keys if k and _norm(k)}
    project_key: str | None = None
    environment: str | None = None
    service: str | None = None
    matched_keys: set[str] = set()

    for w in _words(text):
        clean = _norm(w)
        if clean in keys and clean not in matched_keys:
            project_key = clean
            matched_keys.add(clean)
            continue
        if clean in COMMON_ENVS:
            environment = COMMON_ENVS[clean]
            continue
        if clean in _COMMON_SERVICE:
            if clean in ("app", "web"):
                service = "api"
            elif clean in ("db", "postgres"):
                service = "postgres" if "postgres" in (text or "").lower() else "db"
            else:
                service = clean

    return {
        "project_key": project_key,
        "environment": environment,
        "service": service,
    }


def parse_dev_project_phrase(
    m_body: str,
    *,
    known_project_keys: list[str],
) -> tuple[str | None, str]:
    """
    Looks for a trailing ' in <project> ' or ' in <key>' clause. Returns (project_key, instruction without clause).
    """
    raw = (m_body or "").strip()
    if not raw:
        return None, raw
    keys = {_norm(k) for k in known_project_keys if k}
    m = re.search(
        r"""(?i)\s+in\s+([a-z0-9][a-z0-9_\-]*)\s*\.?\s*$""",
        raw,
    )
    if m:
        cand = _norm(m.group(1))
        if cand in keys:
            stripped = (raw[: m.start()].rstrip() + raw[m.end() :].rstrip()).strip()
            if stripped.endswith("."):
                stripped = stripped.rstrip()
            return cand, (stripped or raw).strip() or m_body.strip()
    return None, raw
