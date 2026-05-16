# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from typing import Any

# Safe, read-only style probes (no deploy side effects).
PROVIDERS: dict[str, dict[str, Any]] = {
    "vercel": {
        "binary": "vercel",
        "auth_argv": ["vercel", "whoami"],
        "projects_argv": ["vercel", "project", "ls", "--json"],
    },
    "railway": {
        "binary": "railway",
        "auth_argv": ["railway", "whoami"],
    },
    "fly": {
        "binary": "flyctl",
        "auth_argv": ["flyctl", "auth", "whoami"],
    },
    "netlify": {
        "binary": "netlify",
        "auth_argv": ["netlify", "status"],
    },
    "cloudflare": {
        "binary": "wrangler",
        "auth_argv": ["wrangler", "whoami"],
    },
    "github": {
        "binary": "gh",
        "auth_argv": ["gh", "auth", "status"],
    },
}

PROVIDER_IDS: tuple[str, ...] = tuple(sorted(PROVIDERS.keys()))


def get_provider_spec(provider_id: str) -> dict[str, Any] | None:
    pid = (provider_id or "").strip().lower()
    return PROVIDERS.get(pid)
