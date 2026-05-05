import React from 'react';
import {StyleSheet, Text, View} from 'react-native';

import {Button} from '../../components/common/Button';
import {useAuthStore} from '../../store/authStore';

export default function ProfileScreen() {
  const userId = useAuthStore(s => s.userId);
  const logout = useAuthStore(s => s.logout);
  return (
    <View style={styles.c}>
      <Text style={styles.h}>Profile</Text>
      <Text style={styles.l}>User id: {userId}</Text>
      <Button title="Sign out" onPress={() => logout()} />
    </View>
  );
}

const styles = StyleSheet.create({
  c: {flex: 1, padding: 16},
  h: {fontSize: 20, fontWeight: '700'},
  l: {marginVertical: 16},
});
