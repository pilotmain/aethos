/**
 * Governance org APIs — GET /api/v1/governance/*
 * (Spec referenced `/org/*`; Nexa uses `/governance/organizations/...`.)
 */

import { apiFetch } from "@/lib/api/client";

export type GovernanceMeResponse = {
  governance_enabled: boolean;
  default_organization_id: string | null;
  organizations: Array<{ id: string; name: string; enabled: boolean }>;
};

export type OrgMemberRow = {
  user_id: string;
  role: string;
  enabled: boolean;
};

export async function fetchGovernanceMe(): Promise<GovernanceMeResponse> {
  return apiFetch<GovernanceMeResponse>("/governance/me");
}

export async function fetchOrgMembers(orgId: string): Promise<OrgMemberRow[]> {
  const out = await apiFetch<{ members?: OrgMemberRow[] }>(
    `/governance/organizations/${encodeURIComponent(orgId)}/members`,
  );
  return Array.isArray(out.members) ? out.members : [];
}

export async function postOrgMember(orgId: string, body: { user_id: string; role: string }): Promise<void> {
  await apiFetch(`/governance/organizations/${encodeURIComponent(orgId)}/members`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function patchOrgMember(
  orgId: string,
  memberUserId: string,
  body: { role?: string; enabled?: boolean },
): Promise<void> {
  await apiFetch(
    `/governance/organizations/${encodeURIComponent(orgId)}/members/${encodeURIComponent(memberUserId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    },
  );
}
