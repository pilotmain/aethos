#!/usr/bin/env python3
"""
Emit env lines to append to `.env` for local full-feature testing.

python-dotenv gives **last** duplicate key wins — append this block at the **end**
of `.env` so these values override earlier conservative defaults.

Excluded from "flip to true": flags that would break LLMs, host execution, or dev UX
(`NEXA_DISABLE_EXTERNAL_CALLS`, strict privacy, production mode, dry-run-only host, etc.).
"""
from __future__ import annotations

from app.core.config import Settings

# Do not force these to true — they block APIs, force simulate-only host, or lock prod posture.
_DENY_FLIP_TRUE: frozenset[str] = frozenset(
    {
        "nexa_host_executor_dry_run_default",
        "nexa_disable_external_calls",
        "nexa_strict_privacy_mode",
        "nexa_production_mode",
        "nexa_mission_control_sql_purge",
        "nexa_enforce_enterprise_gates",
        "nexa_auto_approve_log_only",
        # Prefer cloud/API keys in .env unless you run Ollama locally.
        "nexa_local_first",
    }
)

# Always emit these at the **end** so they override any mistaken true above.
_FORCE_FALSE_END: dict[str, str] = {
    "NEXA_HOST_EXECUTOR_DRY_RUN_DEFAULT": "false",
    "NEXA_DISABLE_EXTERNAL_CALLS": "false",
    "NEXA_STRICT_PRIVACY_MODE": "false",
    "NEXA_PRODUCTION_MODE": "false",
    "NEXA_MISSION_CONTROL_SQL_PURGE": "false",
    "NEXA_ORCH_REQUIRE_APPROVAL": "false",
    "NEXA_LOCAL_FIRST": "false",
}


def main() -> None:
    header = """
# =============================================================================
# LOCAL FULL-FEATURE TEST PROFILE — appended by scripts/emit_full_feature_env_append.py
# Last occurrence of each key wins. Safe guards are repeated at the bottom as false.
# =============================================================================
""".strip()

    lines: list[str] = [header, ""]

    for name, field in Settings.model_fields.items():
        default = field.default
        if field.default_factory is not None:
            continue
        ann = field.annotation
        origin = getattr(ann, "__origin__", None)
        if origin is not None:
            args = getattr(ann, "__args__", ())
            if bool in args:
                ann = bool
        if ann is not bool:
            continue
        if default is not False:
            continue
        if name in _DENY_FLIP_TRUE:
            continue
        lines.append(f"{name.upper()}=true")

    lines.append("")
    lines.append("# --- guards (must stay false for usable local testing) ---")
    for k, v in _FORCE_FALSE_END.items():
        lines.append(f"{k}={v}")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
