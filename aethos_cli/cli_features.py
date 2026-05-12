# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""``nexa features`` — summarize enabled capability flags from repo ``.env``."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _truthy(val: str) -> bool:
    return val.strip().lower() in ("1", "true", "yes", "on")


def cmd_features() -> int:
    env_path = _repo_root() / ".env"
    if not env_path.is_file():
        print(f"No .env at {env_path}", file=sys.stderr)
        return 1

    raw = env_path.read_text(encoding="utf-8", errors="replace")
    kv: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if m:
            k, v = m.group(1), m.group(2).strip().strip('"').strip("'")
            kv[k] = v

    labels = [
        ("NEXA_HOST_EXECUTOR_ENABLED", "Git / host executor"),
        ("NEXA_NL_TO_CHAIN_ENABLED", "NL → chain"),
        ("NEXA_BROWSER_ENABLED", "Browser automation"),
        ("NEXA_CRON_ENABLED", "Cron jobs"),
        ("NEXA_SOCIAL_ENABLED", "Social posting"),
        ("NEXA_PR_REVIEW_ENABLED", "PR reviews"),
        ("NEXA_SCRAPING_ENABLED", "Web scraping"),
        ("USE_REAL_LLM", "Real LLM calls"),
        ("NEXA_OLLAMA_ENABLED", "Ollama"),
    ]
    seen: set[str] = set()
    print("Enabled features (from .env):\n")
    any_on = False
    for key, label in labels:
        if key in seen:
            continue
        seen.add(key)
        if key not in kv:
            continue
        if _truthy(kv[key]):
            print(f"  ✓ {label:<28} {key}=true")
            any_on = True
        else:
            print(f"  · {label:<28} {key}=false")

    if not any_on:
        print("  (no capability flags parsed as enabled — edit .env or run `nexa setup`)")
    print(f"\nEnv file: {env_path}")
    return 0


__all__ = ["cmd_features"]
