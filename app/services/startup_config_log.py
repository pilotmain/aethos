# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Sanitized process startup config (no API keys, tokens, or full DB credentials)."""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

from app.core.config import get_settings
from app.services.runtime_capabilities import autonomy_test_mode

logger = logging.getLogger(__name__)


def _db_public_summary(url: str) -> str:
    s = (url or "").strip()
    if not s:
        return "database (empty URL)"
    if s.lower().startswith("sqlite:"):
        tail = s.rsplit("/", 1)[-1] if "/" in s else s
        tail = tail.split("?")[0]
        return f"sqlite file={tail[-64:]!s}" if len(tail) < 200 else f"sqlite ({len(s)} chars)"
    u = urlparse(s)
    if not u.hostname:
        return "database (unparsed URL; check DATABASE_URL format)"
    has_user = bool(u.username)
    port = u.port
    pstr = f":{port}" if port else ""
    dbn = (u.path or "/").lstrip("/").split("?")[0]
    return (
        f"{u.scheme} {u.hostname}{pstr} db={dbn[:64]} user_in_url_set={has_user}"
    )


def log_sanitized_nexa_config(component: str) -> None:
    """Log a short config summary. component is `api` or `bot` (or other). No secrets."""
    s = get_settings()
    db = _db_public_summary(s.database_url)
    env_low = (s.app_env or "").strip().lower()
    safety_lines: list[str] = []
    if env_low in ("production", "prod"):
        if not getattr(s, "nexa_safety_policy_strict", False):
            safety_lines.append(
                "WARN: APP_ENV is production but NEXA_SAFETY_POLICY_STRICT is false — "
                "enable strict policy checks for safer deployments."
            )
        if not getattr(s, "nexa_network_external_send_enforced", False):
            safety_lines.append(
                "WARN: APP_ENV is production but NEXA_NETWORK_EXTERNAL_SEND_ENFORCED is false — "
                "HTTP egress is not gated by network_external_send grants."
            )

    lines: list[str] = [
        f"=== Nexa config ({component}) ===",
        f"APP_NAME={s.app_name}",
        f"APP_ENV={s.app_env}",
        f"USE_REAL_LLM={s.use_real_llm}",
        f"DB={db}",
        f"DEV_EXECUTOR_ON_HOST={s.dev_executor_on_host}",
        f"OPERATOR_AUTO_RUN_DEV_EXECUTOR={s.operator_auto_run_dev_executor}",
        f"DEV_AGENT_AUTO_RUN={(os.environ.get('DEV_AGENT_AUTO_RUN') or '').strip() or 'unset'}",
        f"DEV_AUTO_COMMIT={(os.environ.get('DEV_AUTO_COMMIT') or '').strip() or 'unset'}",
        f"DEV_AUTO_PUSH={(os.environ.get('DEV_AUTO_PUSH') or '').strip() or 'unset'}",
        f"NEXA_WORKSPACE_ROOT={s.nexa_workspace_root}",
        f"NEXA_OPS_PROVIDER={(os.environ.get('NEXA_OPS_PROVIDER') or 'local').strip()}",
        f"NEXA_WEB_ACCESS_ENABLED={s.nexa_web_access_enabled}",
        f"NEXA_SAFETY_POLICY_STRICT={getattr(s, 'nexa_safety_policy_strict', False)}",
        f"NEXA_NETWORK_EXTERNAL_SEND_ENFORCED={getattr(s, 'nexa_network_external_send_enforced', False)}",
        f"NEXA_SECRET_EGRESS_ENFORCED={getattr(s, 'nexa_secret_egress_enforced', False)}",
        f"AETHOS_PRIVACY_MODE={getattr(s, 'aethos_privacy_mode', 'observe')}",
    ]
    if safety_lines:
        lines.extend(safety_lines)
    try:
        s2 = get_settings()
        lines.append(f"NEXA_WORKSPACE_MODE={getattr(s2, 'nexa_workspace_mode', 'regulated')}")
        lines.append(f"NEXA_APPROVALS_ENABLED={getattr(s2, 'nexa_approvals_enabled', True)}")
        if autonomy_test_mode(s2):
            warn = (
                "WARNING: NEXA approvals are disabled (developer autonomy test mode). "
                "Intended for local development only."
            )
            lines.append(warn)
            logger.warning(warn)
            print(warn, flush=True)
    except Exception:  # noqa: BLE001
        pass
    block = "\n".join(lines) + "\n=== end Nexa config ==="
    print(block, flush=True)
    logger.info("sanitized_nexa_config component=%s db=%s", component, db)


def maybe_log_llm_key_hint() -> None:
    s = get_settings()
    if not s.use_real_llm and (s.anthropic_api_key or s.openai_api_key):
        print(
            "HINT: You have API keys in the environment, but USE_REAL_LLM is false. "
            "In the repo root .env, set USE_REAL_LLM=true (unquoted) and restart.",
            flush=True,
        )
