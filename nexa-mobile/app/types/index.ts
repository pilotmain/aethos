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
