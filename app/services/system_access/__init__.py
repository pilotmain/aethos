# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace-scoped system access (Phase 39) — safe defaults; extend with governance."""

from app.services.system_access.files import read_text_file
from app.services.system_access.permissions import assert_workspace_path
from app.services.system_access.shell import run_allowlisted_shell
from app.services.system_access.shell_allowlist import DEFAULT_SAFE_SHELL_ALLOWLIST

__all__ = [
    "DEFAULT_SAFE_SHELL_ALLOWLIST",
    "assert_workspace_path",
    "read_text_file",
    "run_allowlisted_shell",
]
