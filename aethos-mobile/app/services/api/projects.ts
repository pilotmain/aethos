import {api} from './client';

import type {ProjectSummary} from '../../types';

export async function listProjects(orgId: string): Promise<{projects: ProjectSummary[]}> {
  const {data} = await api.get(`/mobile/orgs/${orgId}/projects`);
  return data;
}

export async function createProject(
  name: string,
  goal: string,
  organizationId?: string | null,
): Promise<{project: {id: string; name: string; goal: string}}> {
  const {data} = await api.post('/mobile/projects', {
    name,
    goal,
    organization_id: organizationId ?? null,
  });
  return data;
}

export async function getMissionTree(projectId: string): Promise<Record<string, unknown>> {
  const {data} = await api.get(`/mobile/projects/${projectId}/tree`);
  return data;
}
