#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Validate local `.env` by loading it and constructing `Settings` from app/core/config.py.

Usage (from repo root, with venv active):
  python scripts/validate_aethos_env.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def main() -> int:
    env_path = _REPO / ".env"
    if not env_path.is_file():
        print(f"Missing {env_path}")
        return 1

    from dotenv import load_dotenv

    load_dotenv(env_path, override=True)

    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    try:
        s: Settings = get_settings()
    except Exception as exc:  # noqa: BLE001
        print(f"Settings validation failed: {exc}")
        return 1

    def _has_llm(sx: Settings) -> bool:
        return bool(
            (sx.anthropic_api_key or "").strip()
            or (sx.openai_api_key or "").strip()
            or (sx.nexa_llm_api_key or "").strip()
        )

    checks: dict[str, bool] = {
        "Database URL": bool((s.database_url or "").strip()),
        "NEXA_SECRET_KEY (web/crypto)": bool((s.nexa_secret_key or "").strip()),
        "Telegram token": bool((s.telegram_bot_token or "").strip()),
        "LLM credentials (any provider)": _has_llm(s),
        "USE_REAL_LLM": bool(s.use_real_llm),
        "Agent orchestration": bool(s.nexa_agent_orchestration_enabled),
        "ClawHub / skill registry URL": bool((s.nexa_clawhub_api_base or "").strip()),
        "Workspace root": bool((s.nexa_workspace_root or "").strip()),
        "Self-improvement enabled": bool(s.nexa_self_improvement_enabled),
        "Redis optional (not required)": True,
        "Orchestration sandbox mode": bool((s.nexa_sandbox_mode or "").strip()),
    }

    ok_n = sum(1 for v in checks.values() if v)
    print("\nAethOS environment validation (from Settings after load_dotenv)\n")
    print("-" * 56)
    for name, ok in checks.items():
        icon = "yes" if ok else "no "
        print(f"  [{icon}] {name}")
    print("-" * 56)
    print(f"\nSummary: {ok_n}/{len(checks)} checks positive")
    print("\nNotes:")
    print("  - LLM features need real keys in .env (Anthropic/OpenAI/nexa_llm_*).")
    print("  - Optional integrations (GitHub, Vercel, Redis, S3) are documented in .env.example.")
    from app.services.llm_intelligence import resolve_effective_anthropic_model_id

    print("  - Set NEXA_SELF_IMPROVEMENT_ENABLED=true to enable self-improvement proposals.")
    print(
        f"  - LLM intelligence: {s.nexa_llm_intelligence_level} "
        f"(effective Anthropic model: {resolve_effective_anthropic_model_id(s)})"
    )
    print()

    critical = checks["Database URL"] and checks["NEXA_SECRET_KEY (web/crypto)"]
    return 0 if critical else 1


if __name__ == "__main__":
    raise SystemExit(main())
