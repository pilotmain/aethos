import {useMutation, useQueryClient} from '@tanstack/react-query';
import React, {useLayoutEffect, useMemo, useState} from 'react';
import {Alert, ScrollView, StyleSheet, View} from 'react-native';
import {SegmentedButtons, Text} from 'react-native-paper';
import type {StackScreenProps} from '@react-navigation/stack';

import type {MissionStackParamList} from '../../navigation/types';
import {patchTaskStatus} from '../../services/api/tasks';

type Props = StackScreenProps<MissionStackParamList, 'TaskDetail'>;

const STATUS_OPTIONS = [
  {value: 'pending', label: 'To do'},
  {value: 'in_progress', label: 'Doing'},
  {value: 'done', label: 'Done'},
  {value: 'blocked', label: 'Blocked'},
];

export default function TaskDetailScreen({route, navigation}: Props) {
  const {task} = route.params;
  const qc = useQueryClient();
  const [status, setStatus] = useState(task.status);

  useLayoutEffect(() => {
    navigation.setOptions({title: task.title});
  }, [navigation, task.title]);

  const mutation = useMutation({
    mutationFn: (next: string) => patchTaskStatus(task.id, next),
    onSuccess: (_d, next) => {
      setStatus(next);
      void qc.invalidateQueries({queryKey: ['mission-tree', route.params.projectId]});
    },
    onError: (e: unknown) => {
      const msg = e instanceof Error ? e.message : 'Update failed';
      Alert.alert('Error', msg);
    },
  });

  const buttons = useMemo(
    () =>
      STATUS_OPTIONS.map(o => ({
        value: o.value,
        label: o.label,
      })),
    [],
  );

  return (
    <ScrollView contentContainerStyle={styles.c}>
      <Text variant="bodyMedium" style={styles.meta}>
        Updated {task.updated_at}
      </Text>
      {task.description ? (
        <Text variant="bodyLarge" style={styles.desc}>
          {task.description}
        </Text>
      ) : (
        <Text style={styles.muted}>No description</Text>
      )}
      <Text variant="titleSmall" style={styles.section}>
        Status
      </Text>
      <SegmentedButtons
        value={status}
        onValueChange={next => {
          setStatus(next);
          mutation.mutate(next);
        }}
        buttons={buttons}
        style={styles.seg}
      />
      {task.assigned_to ? (
        <Text style={styles.meta}>Assigned: {task.assigned_to}</Text>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  c: {padding: 16, backgroundColor: '#09090b'},
  meta: {color: '#a1a1aa', marginBottom: 12},
  desc: {color: '#fafafa', marginBottom: 16},
  muted: {color: '#71717a', marginBottom: 16},
  section: {color: '#fafafa', marginBottom: 8},
  seg: {marginBottom: 16},
});
