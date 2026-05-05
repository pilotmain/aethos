import React from 'react';
import {StyleSheet, Text, TouchableOpacity, View} from 'react-native';

import {useWorkspaceStore} from '../../store/workspaceStore';

export default function WorkspaceSettingsScreen({navigation}: {navigation: {navigate: (n: string) => void}}) {
  const activeOrgId = useWorkspaceStore(s => s.activeOrgId);
  return (
    <View style={styles.c}>
      <Text style={styles.h}>Workspace</Text>
      <Text style={styles.l}>Active org id: {activeOrgId ?? 'none'}</Text>
      <TouchableOpacity onPress={() => navigation.navigate('Budget')} style={styles.link}>
        <Text style={styles.linkT}>Budget</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={() => navigation.navigate('Usage')} style={styles.link}>
        <Text style={styles.linkT}>Usage</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  c: {flex: 1, padding: 16},
  h: {fontSize: 20, fontWeight: '700'},
  l: {marginVertical: 12, color: '#4b5563'},
  link: {paddingVertical: 12},
  linkT: {color: '#2563eb', fontWeight: '600'},
});
