import React from 'react';
import {StyleSheet, Text, View} from 'react-native';

import {Card} from '../../components/common/Card';
import {useAuthStore} from '../../store/authStore';
import {useWorkspaceStore} from '../../store/workspaceStore';

export default function DashboardScreen() {
  const userId = useAuthStore(s => s.userId);
  const activeOrg = useWorkspaceStore(s => s.activeOrgId);
  return (
    <View style={styles.c}>
      <Text style={styles.h}>Overview</Text>
      <Card>
        <Text style={styles.l}>Signed in as {userId}</Text>
        <Text style={styles.l}>Active workspace: {activeOrg ?? 'none'}</Text>
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  c: {flex: 1, padding: 16},
  h: {fontSize: 22, fontWeight: '700', marginBottom: 12},
  l: {marginVertical: 4},
});
