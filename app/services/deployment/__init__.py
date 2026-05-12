# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Generic CLI-based deployment detection and execution."""

from app.services.deployment.detector import DeploymentDetector
from app.services.deployment.executor import DeploymentExecutor
from app.services.deployment.project_layout import find_project_root

__all__ = ["DeploymentDetector", "DeploymentExecutor", "find_project_root"]
