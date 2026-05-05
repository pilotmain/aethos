import React from 'react';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import {createStackNavigator} from '@react-navigation/stack';

import type {ChatStackParamList, MissionStackParamList, WorkspaceStackParamList} from './types';
import ChatDetailScreen from '../screens/Chat/ChatDetailScreen';
import ChatListScreen from '../screens/Chat/ChatListScreen';
import DashboardScreen from '../screens/Dashboard/DashboardScreen';
import MissionTreeScreen from '../screens/Mission/MissionTreeScreen';
import ProjectDetailScreen from '../screens/Mission/ProjectDetailScreen';
import ProjectsScreen from '../screens/Mission/ProjectsScreen';
import TaskDetailScreen from '../screens/Mission/TaskDetailScreen';
import ProfileScreen from '../screens/Profile/ProfileScreen';
import TeamScreen from '../screens/Team/TeamScreen';
import BudgetScreen from '../screens/Workspace/BudgetScreen';
import UsageScreen from '../screens/Workspace/UsageScreen';
import WorkspaceSettingsScreen from '../screens/Workspace/WorkspaceSettingsScreen';
import WorkspaceSelectScreen from '../screens/Auth/WorkspaceSelectScreen';

const Tab = createBottomTabNavigator();
const Mission = createStackNavigator<MissionStackParamList>();
const Chat = createStackNavigator<ChatStackParamList>();
const Workspace = createStackNavigator<WorkspaceStackParamList>();

function MissionStack() {
  return (
    <Mission.Navigator>
      <Mission.Screen name="Projects" component={ProjectsScreen} options={{title: 'Projects'}} />
      <Mission.Screen name="ProjectDetail" component={ProjectDetailScreen} />
      <Mission.Screen name="MissionTree" component={MissionTreeScreen} options={{title: 'Goal tree'}} />
      <Mission.Screen name="TaskDetail" component={TaskDetailScreen} />
    </Mission.Navigator>
  );
}

function ChatStack() {
  return (
    <Chat.Navigator>
      <Chat.Screen name="ChatList" component={ChatListScreen} options={{title: 'Chat'}} />
      <Chat.Screen name="ChatDetail" component={ChatDetailScreen} />
    </Chat.Navigator>
  );
}

function WorkspaceStack() {
  return (
    <Workspace.Navigator>
      <Workspace.Screen name="WorkspaceHome" component={WorkspaceSettingsScreen} options={{title: 'Workspace'}} />
      <Workspace.Screen name="Budget" component={BudgetScreen} />
      <Workspace.Screen name="Usage" component={UsageScreen} />
    </Workspace.Navigator>
  );
}

export default function MainTabs() {
  return (
    <Tab.Navigator screenOptions={{headerShown: false}}>
      <Tab.Screen name="Dashboard" component={DashboardScreen} />
      <Tab.Screen name="Mission" component={MissionStack} />
      <Tab.Screen name="Chat" component={ChatStack} />
      <Tab.Screen name="Team" component={TeamScreen} />
      <Tab.Screen name="Workspace" component={WorkspaceStack} />
      <Tab.Screen name="Workspaces" component={WorkspaceSelectScreen} options={{title: 'Switch org'}} />
      <Tab.Screen name="Profile" component={ProfileScreen} />
    </Tab.Navigator>
  );
}
