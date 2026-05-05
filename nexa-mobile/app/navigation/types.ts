import type {ProjectSummary} from '../types';

export type MissionStackParamList = {
  Projects: undefined;
  ProjectDetail: {project: ProjectSummary};
  MissionTree: {projectId: string};
  TaskDetail: undefined;
};

export type ChatStackParamList = {
  ChatList: undefined;
  ChatDetail: undefined;
};

export type WorkspaceStackParamList = {
  WorkspaceHome: undefined;
  Budget: undefined;
  Usage: undefined;
};
