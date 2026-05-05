"""
Resource helpers for multi-tenant isolation (Phase 29).

Mission Control and other stores attach optional ``organization_id`` / ``team_id``.
Use :meth:`ResourceIsolation.resolve_org_filter` with the caller's workspace ids.
"""

from __future__ import annotations

from typing import Any

from app.services.rbac.organization_service import OrganizationService


class ResourceIsolation:
    """Org membership checks + helpers for filtering resources by tenant."""

    def __init__(self, org_service: OrganizationService | None = None) -> None:
        self.org_service = org_service or OrganizationService()

    def organization_ids_for_user(self, user_id: str) -> list[str]:
        """All organizations the user belongs to (active memberships)."""
        return [o.id for o in self.org_service.list_organizations_for_user(user_id)]

    def enforce_org_access(
        self,
        org_id: str | None,
        user_id: str,
        permission: str = "view_all",
    ) -> bool:
        """Return True if user may perform ``permission`` in ``org_id``."""
        if not org_id:
            return False
        return self.org_service.check_permission(org_id, user_id, permission)

    def resolve_org_filter(
        self,
        user_id: str,
        *,
        active_org_id: str | None,
    ) -> tuple[list[str] | None, str | None]:
        """
        Returns ``(allowed_org_ids, active_org_id)`` for query filtering.

        - When RBAC is off or user has no orgs, returns ``(None, active_org_id)`` —
          callers should not filter by org (legacy behaviour).
        - Otherwise ``allowed_org_ids`` lists orgs the user belongs to; callers can
          restrict rows to ``organization_id IN (...) OR organization_id IS NULL``.
        """
        allowed = self.organization_ids_for_user(user_id)
        if not allowed:
            return None, active_org_id
        if active_org_id and active_org_id in allowed:
            return allowed, active_org_id
        return allowed, active_org_id

    def enrich_resource_flags(
        self,
        *,
        user_id: str,
        resource: dict[str, Any],
        org_field: str = "organization_id",
    ) -> dict[str, Any]:
        """Add coarse-grained edit/delete hints for UIs (best-effort)."""
        oid = resource.get(org_field)
        if not oid:
            resource["user_can_edit"] = True
            resource["user_can_delete"] = False
            return resource
        resource["user_can_edit"] = self.enforce_org_access(
            str(oid), user_id, "manage_tasks"
        )
        resource["user_can_delete"] = self.enforce_org_access(
            str(oid), user_id, "delete_project"
        )
        return resource


__all__ = ["ResourceIsolation"]
