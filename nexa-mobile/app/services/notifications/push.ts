import AsyncStorage from '@react-native-async-storage/async-storage';
import notifee, {AndroidImportance} from '@notifee/react-native';
import {Platform} from 'react-native';

import {api} from '../api/client';

const CHANNEL_ID = 'nexa_default';
const INSTALL_TOKEN_KEY = 'nexa_push_install_token';

/**
 * Registers a stable device token with the API and prepares notification channels.
 * Full FCM/APNs delivery can be wired later; the backend stores tokens for outbound push.
 */
export async function setupPushNotifications(): Promise<void> {
  await notifee.createChannel({
    id: CHANNEL_ID,
    name: 'Nexa',
    importance: AndroidImportance.HIGH,
    sound: 'default',
  });

  let token = await AsyncStorage.getItem(INSTALL_TOKEN_KEY);
  if (!token) {
    token = `nexa-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
    await AsyncStorage.setItem(INSTALL_TOKEN_KEY, token);
  }

  try {
    await api.post('/mobile/push-token', {
      push_token: token,
      platform: Platform.OS === 'ios' ? 'ios' : 'android',
    });
  } catch {
    // Auth or network not ready yet — RootNavigator will retry on next app launch if needed.
  }
}

export async function showLocalNotice(title: string, body: string, data?: Record<string, string>): Promise<void> {
  await notifee.displayNotification({
    title,
    body,
    data,
    android: {channelId: CHANNEL_ID, importance: AndroidImportance.HIGH},
    ios: {sound: 'default'},
  });
}
