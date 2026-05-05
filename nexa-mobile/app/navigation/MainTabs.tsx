import React from 'react';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import {createStackNavigator} from '@react-navigation/stack';

import type {
  ChatStackParamList,
  MissionStackParamList,
  TeamStackParamList,
  WorkspaceStackParamList,
} from './types';
import ChatDetailScreen from '../screens/Chat/ChatDetailScreen';
import ChatListScreen from '../screens/Chat/ChatListScreen';
import DashboardScreen from '../screens/Dashboard/DashboardScreen';
import CreateTaskScreen from '../screens/Mission/CreateTaskScreen';
import MissionTreeScreen from '../screens/Mission/MissionTreeScreen';
import ProjectDetailScreen from '../screens/Mission/ProjectDetailScreen';
import ProjectsScreen from '../screens/Mission/ProjectsScreen';
import TaskDetailScreen from '../screens/Mission/TaskDetailScreen';
import ProfileScreen from '../screens/Profile/ProfileScreen';
import InviteScreen from '../screens/Team/InviteScreen';
import MemberDetailScreen from '../screens/Team/MemberDetailScreen';
import TeamScreen from '../screens/Team/TeamScreen';
import BudgetScreen from '../screens/Workspace/BudgetScreen';
import BudgetSettingsScreen from '../screens/Workspace/BudgetSettingsScreen';
import UsageHistoryScreen from '../screens/Workspace/UsageHistoryScreen';
import UsageScreen from '../screens/Workspace/UsageScreen';
import WorkspaceSettingsScreen from '../screens/Workspace/WorkspaceSettingsScreen';
import WorkspaceSelectScreen from '../screens/Auth/WorkspaceSelectScreen';

const Tab = createBottomTabNavigator();
const Mission = createStackNavigator<MissionStackParamList>();
const Chat = createStackNavigator<ChatStackParamList>();
const Workspace = createStackNavigator<WorkspaceStackParamList>();
const Team = createStackNavigator<TeamStackParamList>();

const stackScreenOptions = {
  headerStyle: {backgroundColor: '#09090b'},
  headerTintColor: '#fafafa',
  headerShadowVisible: false,
};

function MissionStack() {
  return (
    <Mission.Navigator screenOptions={stackScreenOptions}>
      <Mission.Screen name="Projects" component={ProjectsScreen} options={{title: 'Projects'}} />
      <Mission.Screen name="ProjectDetail" component={ProjectDetailScreen} />
      <Mission.Screen name="MissionTree" component={MissionTreeScreen} options={{title: 'Goal tree'}} />
      <Mission.Screen name="TaskDetail" component={TaskDetailScreen} />
      <Mission.Screen name="CreateTask" component={CreateTaskScreen} />
    </Mission.Navigator>
  );
}

function ChatStack() {
  return (
    <Chat.Navigator screenOptions={stackScreenOptions}>
      <Chat.Screen name="ChatList" component={ChatListScreen} options={{title: 'Chat'}} />
      <Chat.Screen name="ChatDetail" component={ChatDetailScreen} />
    </Chat.Navigator>
  );
}

function WorkspaceStack() {
  return (
    <Workspace.Navigator screenOptions={stackScreenOptions}>
      <Workspace.Screen name="WorkspaceHome" component={WorkspaceSettingsScreen} options={{title: 'Workspace'}} />
      <Workspace.Screen name="Budget" component={BudgetScreen} />
      <Workspace.Screen name="Usage" component={UsageScreen} />
      <Workspace.Screen name="BudgetSettings" component={BudgetSettingsScreen} options={{title: 'Budget limits'}} />
      <Workspace.Screen name="UsageHistory" component={UsageHistoryScreen} options={{title: 'Usage history'}} />
    </Workspace.Navigator>
  );
}

function TeamStack() {
  return (
    <Team.Navigator screenOptions={stackScreenOptions}>
      <Team.Screen name="TeamHome" component={TeamScreen} options={{title: 'Team'}} />
      <Team.Screen name="MemberDetail" component={MemberDetailScreen} options={{title: 'Member'}} />
      <Team.Screen name="Invite" component={InviteScreen} options={{title: 'Invite'}} />
    </Team.Navigator>
  );
}

export default function MainTabs() {
  return (
    <Tab.Navigator screenOptions={{headerShown: false}}>
      <Tab.Screen name="Dashboard" component={DashboardScreen} />
      <Tab.Screen name="Mission" component={MissionStack} />
      <Tab.Screen name="Chat" component={ChatStack} />
      <Tab.Screen name="Team" component={TeamStack} />
      <Tab.Screen name="Workspace" component={WorkspaceStack} />
      <Tab.Screen name="Workspaces" component={WorkspaceSelectScreen} options={{title: 'Switch org'}} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}
