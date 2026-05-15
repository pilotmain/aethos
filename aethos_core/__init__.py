# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Small open-core compatibility package for local AethOS development.

The full project may install ``aethos-core`` from GitHub, but local/offline
workspaces still need these public helpers so the app and tests can boot.
"""

__all__ = ["plugin_manager", "response_formatter"]
