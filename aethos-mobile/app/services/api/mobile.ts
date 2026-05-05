import {api} from './client';

import type {DashboardMetrics} from '../../types';

export async function fetchDashboard(): Promise<DashboardMetrics> {
  const {data} = await api.get('/mobile/dashboard');
  return data as DashboardMetrics;
}

export type MobileSyncPayload = {
  projects: {
    id: string;
    name: string;
    goal: string;
    status: string;
    organization_id?: string | null;
    updated_at: string;
  }[];
  tasks: {
    id: string;
    title: string;
    description?: string | null;
    status: string;
    project_id?: string | null;
    assigned_to?: string | null;
    updated_at: string;
  }[];
  team: {id: string; user_id: string; user_name?: string | null; role: string}[];
  budget: Record<string, unknown>;
  timestamp: string;
};

export async function fetchMobileSync(): Promise<MobileSyncPayload> {
  const {data} = await api.get('/mobile/sync');
  return data as MobileSyncPayload;
}
