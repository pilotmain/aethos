import React, {useCallback, useEffect, useState} from 'react';
import {FlatList, RefreshControl, StyleSheet, Text, TouchableOpacity, View} from 'react-native';
import type {StackScreenProps} from '@react-navigation/stack';

import {ProgressBar} from '../../components/mission/ProgressBar';
import type {MissionStackParamList} from '../../navigation/types';
import {listProjects} from '../../services/api/projects';
import type {ProjectSummary} from '../../types';
import {useWorkspaceStore} from '../../store/workspaceStore';

type Props = StackScreenProps<MissionStackParamList, 'Projects'>;

export default function ProjectsScreen({navigation}: Props) {
  const activeOrgId = useWorkspaceStore(s => s.activeOrgId);
  const [items, setItems] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!activeOrgId) {
      setItems([]);
      return;
    }
    setLoading(true);
    try {
      const data = await listProjects(activeOrgId);
      setItems(data.projects);
    } finally {
      setLoading(false);
    }
  }, [activeOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <View style={styles.c}>
      {!activeOrgId ? (
        <Text style={styles.warn}>Select a workspace from the Org tab.</Text>
      ) : null}
      <FlatList
        data={items}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={() => void load()} />}
        keyExtractor={p => p.id}
        renderItem={({item}) => (
          <TouchableOpacity
            style={styles.row}
            onPress={() => navigation.navigate('ProjectDetail', {project: item})}>
            <Text style={styles.title}>{item.name}</Text>
            <Text numberOfLines={2} style={styles.goal}>
              {item.goal}
            </Text>
            <ProgressBar progress={item.progress ?? 0} />
            <Text style={styles.meta}>
              Tasks {item.tasks_done ?? 0}/{item.tasks_total ?? 0}
            </Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  c: {flex: 1},
  row: {padding: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: '#e5e7eb'},
  title: {fontWeight: '700', fontSize: 16},
  goal: {color: '#4b5563', marginTop: 6},
  meta: {marginTop: 8, color: '#6b7280', fontSize: 12},
  warn: {padding: 16, color: '#b45309'},
});
