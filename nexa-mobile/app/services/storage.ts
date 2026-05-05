import AsyncStorage from '@react-native-async-storage/async-storage';

const KEYS = {
  token: 'nexa_mobile_token',
};

export async function saveToken(token: string | null): Promise<void> {
  if (token) {
    await AsyncStorage.setItem(KEYS.token, token);
  } else {
    await AsyncStorage.removeItem(KEYS.token);
  }
}

export async function loadToken(): Promise<string | null> {
  return AsyncStorage.getItem(KEYS.token);
}
