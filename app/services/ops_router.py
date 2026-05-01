"""
Parse @ops / ops-agent text into a whitelisted action name and a small JSON-safe payload.
Never passes raw user text to subprocess — only allowlisted service keys and name=value for set env.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.project_parser import parse_ops_project_scopes

_LOG_SERVICES = frozenset({"api", "bot", "worker", "postgres", "db", "redis", "app"})
_DEFAULT_LOG = "api"
_RESTART = frozenset({"api", "bot", "worker", "all"})


def _norm_service(raw: str | None) -> str:
    s = (raw or _DEFAULT_LOG).strip().lower()
    if s in ("app", "web"):
        s = "api"
    if s in _LOG_SERVICES:
        if s in ("db", "postgres"):
            return "postgres"
        return s
    return _DEFAULT_LOG


def _merge_scopes(
    base: dict[str, Any], scopes: dict[str, Any], project_explicit: bool
) -> dict[str, Any]:
    pl = dict(base.get("payload") or {})
    if scopes.get("project_key"):
        pl["project_key"] = scopes["project_key"]
        if project_explicit:
            pl["project_key_explicit"] = True
    if scopes.get("environment"):
        pl["environment"] = scopes["environment"]
    if scopes.get("service"):
        pl["service"] = _norm_service(scopes["service"])
    return {"action": base.get("action"), "payload": pl}


def parse_ops_command(
    text: str,
    *,
    known_project_keys: list[str] | None = None,
    default_environment: str = "staging",
) -> dict[str, Any]:
    """
    Returns {"action": str | None, "payload": dict}.
    `action` is a key in OPS_ACTIONS, or None if not recognized.
    """
    keys = known_project_keys or []
    t = (text or "").strip()
    tlow = t.lower()
    scopes = parse_ops_project_scopes(t, known_project_keys=keys)
    if scopes.get("project_key"):
        project_explicit = True
    else:
        project_explicit = False

    out: dict[str, Any] = {"action": None, "payload": {}}
    if not tlow:
        return out

    if re.search(r"deploy\s+(to\s+)?(production|prod)\b", tlow) or re.search(
        r"\bdeploy\s+pro(?:duction)?\b", tlow
    ) or (scopes.get("environment") in ("production",) and re.search(r"\bdeploy\b", tlow)):
        a = "deploy_production"
        p: dict = {}
        if scopes.get("project_key"):
            p["project_key"] = scopes["project_key"]
        if project_explicit and scopes.get("project_key"):
            p["project_key_explicit"] = True
        if scopes.get("environment"):
            p["environment"] = "production"
        return {"action": a, "payload": p}
    if (
        "deploy staging" in tlow
        or "deploy stage" in tlow
        or re.search(r"deploy\s+(to\s+)?stag(?:ing|e)\b", tlow)
        or tlow.strip() in ("deploy staging",)
    ) or (
        re.search(r"\bdeploy\b", tlow)
        and scopes.get("environment") in ("staging", "local", "dev")
    ):
        a2 = "deploy_staging"
        p2: dict = {}
        if scopes.get("project_key"):
            p2["project_key"] = scopes["project_key"]
        if project_explicit and scopes.get("project_key"):
            p2["project_key_explicit"] = True
        if scopes.get("environment"):
            p2["environment"] = scopes["environment"] or "staging"
        return {"action": a2, "payload": p2}
    if "rollback" in tlow or "roll back" in tlow:
        b = _merge_scopes({"action": "rollback", "payload": {}}, scopes, project_explicit)
        return b

    m_env = re.search(
        r"(?:^|\s)(?:set\s+env|@ops\s+set\s+env)\s+([A-Z_][A-Z0-9_]*)\s*=\s*(\S+)$",
        tlow,
        re.IGNORECASE,
    ) or re.search(
        r"set\s+env\s+([A-Z_][A-Z0-9_]*)\s*=\s*(\S+)", tlow, re.IGNORECASE
    )
    if m_env and "set env" in tlow.replace("  ", " "):
        b = {
            "action": "set_env_var",
            "payload": {
                "key": m_env.group(1).upper()[:64],
                "value": m_env.group(2)[:500],
            },
        }
        return _merge_scopes(b, scopes, project_explicit)

    if re.search(
        r"\bset\s+env\b", tlow
    ) and (mm := re.search(
        r"([A-Z_][A-Z0-9_]*)\s*=\s*(\S+)", tlow, re.IGNORECASE
    )):
        b = {
            "action": "set_env_var",
            "payload": {
                "key": mm.group(1).upper()[:64],
                "value": mm.group(2)[:500],
            },
        }
        return _merge_scopes(b, scopes, project_explicit)

    if re.search(r"\brestart\b", tlow):
        mr = re.search(
            r"restart(?:\s+(?:service|the))?\s+([a-z0-9_]+)\b", tlow, re.IGNORECASE
        )
        pld2: dict[str, str] = {}
        if mr and mr.group(1).lower() in _RESTART:
            pld2["service"] = mr.group(1).lower()
        elif scopes.get("service"):
            pld2["service"] = str(scopes.get("service") or "api").lower()
        else:
            pld2["service"] = "api"
        b = _merge_scopes(
            {
                "action": "restart_service",
                "payload": pld2,
            },
            scopes,
            project_explicit,
        )
        return b

    # Project / provider status (docker compose ps, railway status) — includes "status nexa", "nexa status", …
    _status_word = re.search(r"(?<![a-z0-9_])status(?![a-z0-9_])", tlow)
    if (
        _status_word
        and "logs" not in tlow
        and tlow not in ("worker status",)
        and not re.search(r"^\s*jobs?\s+status\b", tlow)
        and not re.search(r"\bset env\b", tlow)
    ):
        return _merge_scopes(
            {"action": "status", "payload": {}},
            scopes,
            project_explicit,
        )

    st_short = tlow in (
        "health",
        "hb",
        "worker",
    ) or (
        re.match(r"^health(\s+\S+)?$", tlow, re.IGNORECASE) and "logs" not in tlow
    )
    if tlow in ("worker status",):
        st_short = True
    if st_short or (
        "health" in tlow
        and "logs" not in tlow
        and len(tlow) < 120
        and not re.search(
            r"\bdeploy|restart|rollback|queue|jobs|set env\b", tlow
        )
    ):
        return _merge_scopes({"action": "health", "payload": {}}, scopes, project_explicit)

    if re.search(r"^\s*logs?\b", tlow) or re.search(
        r"\b(?:show\s+)?logs?\b", tlow, re.IGNORECASE
    ):
        ml = re.search(r"logs(?:\s+for)?\s+([a-z0-9_]+)\b", tlow, re.IGNORECASE) or re.search(
            r"\b(?:show\s+)?logs?\s+([a-z0-9_]+)\b", tlow, re.IGNORECASE
        )
        pk = scopes.get("project_key")
        if scopes.get("service"):
            svc = _norm_service(scopes["service"])
        elif ml:
            g = ml.group(1).lower()
            if pk and g == str(pk).lower():
                svc = _DEFAULT_LOG
            else:
                svc = _norm_service(g)
        else:
            svc = _DEFAULT_LOG
        pld = {"service": svc}
        b = _merge_scopes(
            {
                "action": "logs",
                "payload": pld,
            },
            scopes,
            project_explicit,
        )
        return b

    if tlow in ("queue", "dev queue", "q") or tlow.startswith("queue "):
        return _merge_scopes({"action": "queue", "payload": {}}, scopes, project_explicit)
    if tlow in ("jobs", "job", "list", "job list") or (tlow == "job"):
        return _merge_scopes({"action": "jobs", "payload": {}}, scopes, project_explicit)

    if re.search(r"\bdeploy\b", tlow) and "set env" not in tlow.replace("  ", " "):
        pld: dict[str, str | bool] = {}
        if scopes.get("project_key"):
            pld["project_key"] = scopes["project_key"]  # type: ignore[assignment]
        if project_explicit and scopes.get("project_key"):
            pld["project_key_explicit"] = True
        denv = (default_environment or "staging").lower()
        if denv in ("production", "prod"):
            act = "deploy_production"
        else:
            act = "deploy_staging"
        pld["environment"] = scopes.get("environment") or denv
        b = _merge_scopes(
            {
                "action": act,
                "payload": pld,
            },
            scopes,
            project_explicit,
        )
        if act == "deploy_staging" and pld.get("environment") in ("production", "prod", "pro"):
            b = _merge_scopes(
                {
                    "action": "deploy_production",
                    "payload": pld,
                },
                scopes,
                project_explicit,
            )
        return b

    return out
