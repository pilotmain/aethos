import {api} from './client';

export async function budgetSummary(orgId: string) {
  const {data} = await api.get(`/mobile/orgs/${orgId}/budget-summary`);
  return data as Record<string, unknown>;
}
