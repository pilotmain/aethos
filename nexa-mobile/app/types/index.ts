export type OrgSummary = {
  id: string;
  name: string;
  slug: string;
  role?: string | null;
};

export type ProjectSummary = {
  id: string;
  name: string;
  goal: string;
  status?: string;
  progress?: number;
  tasks_done?: number;
  tasks_total?: number;
};

export type ChatMessage = {
  id: string;
  text: string;
  isUser: boolean;
  createdAt: Date;
};

export type MissionTask = {
  id: string;
  title: string;
  description?: string | null;
  status: string;
  assigned_to?: string | null;
  updated_at: string;
};

export type DashboardMetrics = {
  active_projects: number;
  team_members: number;
  total_tasks: number;
  in_progress_tasks: number;
  budget_used: number;
  budget_limit: number;
  budget_percentage: number;
  recent_tasks: {id: string; title: string; status: string}[];
  active_organization_id: string | null;
};
