from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.project import Project


class OpsProvider(ABC):
    """
    Pluggable cloud / deploy backend for Nexa Ops. Fixed `argv` only (no user shell).
    """

    name: str = "base"
    key: str = "base"

    @abstractmethod
    def execute(
        self,
        action_name: str,
        project: "Project",
        payload: dict[str, Any],
    ) -> str:
        pass

    def execute_safe(
        self, action_name: str, project: "Project", payload: dict[str, Any]
    ) -> str:
        try:
            return self.execute(action_name, project, payload)
        except Exception as exc:  # noqa: BLE001
            return f"Nexa: provider error ({self.key}): {exc!s}"[:2500]
