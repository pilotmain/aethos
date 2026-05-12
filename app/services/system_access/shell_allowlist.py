# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Expanded argv allowlists for safe host tooling (Phase 42).

Wire these into approval flows — :func:`~app.services.system_access.shell.run_allowlisted_shell`
never bypasses human approval for risky workspaces.
"""

from __future__ import annotations

# Phase 42 — read-only git / inspection (exact argv tuples only).
GIT_READ_ALLOWLIST: frozenset[tuple[str, ...]] = frozenset(
    {
        ("git", "status"),
        ("git", "status", "--porcelain"),
        ("git", "diff"),
        ("git", "diff", "--name-only"),
        ("git", "branch"),
        ("git", "log", "--oneline", "-n", "20"),
        ("git", "rev-parse", "--show-toplevel"),
    }
)

# Common test runners (repo must still be allowlisted by workspace policy upstream).
TEST_RUNNER_ALLOWLIST: frozenset[tuple[str, ...]] = frozenset(
    {
        ("pytest",),
        ("python", "-m", "pytest"),
        ("npm", "test"),
        ("npm", "run", "test"),
        ("pnpm", "test"),
        ("yarn", "test"),
    }
)

DEFAULT_SAFE_SHELL_ALLOWLIST: frozenset[tuple[str, ...]] = frozenset().union(
    GIT_READ_ALLOWLIST,
    TEST_RUNNER_ALLOWLIST,
)

__all__ = [
    "DEFAULT_SAFE_SHELL_ALLOWLIST",
    "GIT_READ_ALLOWLIST",
    "TEST_RUNNER_ALLOWLIST",
]
