# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator-quality error types for deploy / provider flows (Phase 2 Step 4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OperatorDeployError(Exception):
    """Base class for structured operator-facing deploy errors."""

    message: str
    suggestions: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "error_class": self.__class__.__name__,
            "message": self.message,
            "suggestions": list(self.suggestions),
            "details": dict(self.details),
        }


class ProjectResolutionError(OperatorDeployError):
    """Named project could not be resolved uniquely."""


class ProviderAuthenticationError(OperatorDeployError):
    """Provider CLI exists but is not authenticated."""


class ProviderCliMissingError(OperatorDeployError):
    """Provider CLI binary not found on PATH."""


class WorkspaceValidationError(OperatorDeployError):
    """Repo / workspace failed validation (missing markers, paths, etc.)."""


class DeploymentContextError(OperatorDeployError):
    """Context could not be assembled for deployment (composite / unknown)."""
