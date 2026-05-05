import {api} from './client';

import type {OrgSummary} from '../../types';

export async function listOrgs(): Promise<{
  organizations: OrgSummary[];
  active_organization_id: string | null;
}> {
  const {data} = await api.get('/mobile/orgs');
  return data;
}

export async function createOrg(name: string, slug?: string): Promise<{organization: OrgSummary}> {
  const {data} = await api.post('/mobile/orgs', {name, slug});
  return data;
}

export async function setActiveOrg(orgId: string): Promise<void> {
  await api.post(`/mobile/orgs/${orgId}/active`);
}

export async function listOrgMembers(orgId: string) {
  const {data} = await api.get(`/mobile/orgs/${orgId}/members`);
  return data as {members: {id: string; user_id: string; user_name?: string; role: string}[]};
}
