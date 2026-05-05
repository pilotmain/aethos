/** Future: derive RBAC flags from org role via GET /mobile/orgs. */
export function usePermissions(_orgId: string | null) {
  return {canManageMembers: false, canCreateProject: true};
}
