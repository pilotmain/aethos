import React, {useEffect} from 'react';
import {StatusBar} from 'react-native';
import {SafeAreaProvider} from 'react-native-safe-area-context';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {MD3DarkTheme, PaperProvider} from 'react-native-paper';

import RootNavigator from './app/navigation/RootNavigator';
import {syncEngine} from './app/services/offline/sync-engine';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {retry: 1, staleTime: 30_000},
  },
});

const paperTheme = {
  ...MD3DarkTheme,
  colors: {
    ...MD3DarkTheme.colors,
    background: '#09090b',
    surface: '#18181b',
    primary: '#818cf8',
    onSurface: '#fafafa',
    outline: '#3f3f46',
  },
};

export default function App() {
  useEffect(() => {
    void syncEngine.init().catch(() => undefined);
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <PaperProvider theme={paperTheme}>
        <SafeAreaProvider>
          <StatusBar barStyle="light-content" backgroundColor="#09090b" />
          <RootNavigator />
        </SafeAreaProvider>
      </PaperProvider>
    </QueryClientProvider>
  );
}
