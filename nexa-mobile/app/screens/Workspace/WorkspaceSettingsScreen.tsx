import React from 'react';
import {StyleSheet, Text, TouchableOpacity, View} from 'react-native';
import type {StackScreenProps} from '@react-navigation/stack';

import type {WorkspaceStackParamList} from '../../navigation/types';
import {useWorkspaceStore} from '../../store/workspaceStore';

type Props = StackScreenProps<WorkspaceStackParamList, 'WorkspaceHome'>;

export default function WorkspaceSettingsScreen({navigation}: Props) {
  const activeOrgId = useWorkspaceStore(s => s.activeOrgId);
  return (
    <View style={styles.c}>
      <Text style={styles.h}>Workspace</Text>
      <Text style={styles.l}>Active org id: {activeOrgId ?? 'none'}</Text>
      <TouchableOpacity onPress={() => navigation.navigate('Budget')} style={styles.link}>
        <Text style={styles.linkT}>Budget</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={() => navigation.navigate('BudgetSettings')} style={styles.link}>
        <Text style={styles.linkT}>Budget limits</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={() => navigation.navigate('Usage')} style={styles.link}>
        <Text style={styles.linkT}>Usage</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={() => navigation.navigate('UsageHistory')} style={styles.link}>
        <Text style={styles.linkT}>Usage history</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  c: {flex: 1, padding: 16, backgroundColor: '#09090b'},
  h: {fontSize: 20, fontWeight: '700', color: '#fafafa'},
  l: {marginVertical: 12, color: '#a1a1aa'},
  link: {paddingVertical: 12},
  linkT: {color: '#a5b4fc', fontWeight: '600'},
});
