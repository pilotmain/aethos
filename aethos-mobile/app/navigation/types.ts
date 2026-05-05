import type {MissionTask, ProjectSummary} from '../types';

export type MissionStackParamList = {
  Projects: undefined;
  ProjectDetail: {project: ProjectSummary};
  MissionTree: {projectId: string};
  TaskDetail: {projectId: string; task: MissionTask};
  CreateTask: {projectId: string; projectName: string};
};

export type TeamStackParamList = {
  TeamHome: undefined;
  MemberDetail: {member: {user_id: string; user_name?: string | null; role: string}};
  Invite: undefined;
};

export type ChatStackParamList = {
  ChatList: undefined;
  ChatDetail: undefined;
};

export type WorkspaceStackParamList = {
  WorkspaceHome: undefined;
  Budget: undefined;
  Usage: undefined;
  BudgetSettings: undefined;
  UsageHistory: undefined;
};
