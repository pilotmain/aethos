import React, {useEffect} from 'react';
import {NavigationContainer} from '@react-navigation/native';
import {createStackNavigator} from '@react-navigation/stack';

import {navigationRef} from './navigationRef';
import {setAuthHeader} from '../services/api/client';
import {setupPushNotifications} from '../services/notifications/push';
import {useAuthStore} from '../store/authStore';
import AuthStack from './AuthStack';
import MainTabs from './MainTabs';

const Root = createStackNavigator();

export default function RootNavigator() {
  const token = useAuthStore(s => s.token);

  useEffect(() => {
    setAuthHeader(token);
  }, [token]);

  useEffect(() => {
    if (token) {
      void setupPushNotifications();
    }
  }, [token]);

  return (
    <NavigationContainer ref={navigationRef} key={token ? 'session' : 'guest'}>
      <Root.Navigator screenOptions={{headerShown: false}}>
        {token ? (
          <Root.Screen name="App" component={MainTabs} />
        ) : (
          <Root.Screen name="Auth" component={AuthStack} />
        )}
      </Root.Navigator>
    </NavigationContainer>
  );
}
