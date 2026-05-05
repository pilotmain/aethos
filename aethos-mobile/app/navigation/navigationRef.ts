import {createNavigationContainerRef} from '@react-navigation/native';

export type RootStackParamList = {
  App: undefined;
  Auth: undefined;
};

export const navigationRef = createNavigationContainerRef<RootStackParamList>();
