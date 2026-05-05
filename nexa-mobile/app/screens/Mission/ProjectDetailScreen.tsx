import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import React, {useCallback, useLayoutEffect, useMemo} from 'react';
import {
  PanResponder,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import {ActivityIndicator, Surface} from 'react-native-paper';
import type {StackScreenProps} from '@react-navigation/stack';

import type {MissionStackParamList} from '../../navigation/types';
import {getMissionTree} from '../../services/api/projects';
import {patchTaskStatus} from '../../services/api/tasks';
import {syncEngine} from '../../services/offline/sync-engine';
import type {MissionTask} from '../../types';

type Props = StackScreenProps<MissionStackParamList, 'ProjectDetail'>;

const COLUMN_ORDER = ['pending', 'in_progress', 'done', 'blocked'] as const;

const COLUMN_LABEL: Record<(typeof COLUMN_ORDER)[number], string> = {
  pending: 'To do',
  in_progress: 'In progress',
  done: 'Done',
  blocked: 'Blocked',
};

type TreePayload = {
  project?: {name?: string; goal?: string};
  tasks?: {items?: MissionTask[]};
};

function statusIndex(s: string): number {
  const i = COLUMN_ORDER.indexOf(s as (typeof COLUMN_ORDER)[number]);
  return i >= 0 ? i : 0;
}

function moveStatus(current: string, delta: number): string {
  const i = statusIndex(current);
  const n = Math.max(0, Math.min(COLUMN_ORDER.length - 1, i + delta));
  return COLUMN_ORDER[n];
}

function groupTasks(items: MissionTask[]) {
  const cols: Record<(typeof COLUMN_ORDER)[number], MissionTask[]> = {
    pending: [],
    in_progress: [],
    done: [],
    blocked: [],
  };
  for (const t of items) {
    const k = t.status as (typeof COLUMN_ORDER)[number];
    if (k in cols) {
      cols[k].push(t);
    } else {
      cols.pending.push(t);
    }
  }
  return cols;
}

export default function ProjectDetailScreen({route, navigation}: Props) {
  const {project} = route.params;
  const qc = useQueryClient();

  useLayoutEffect(() => {
    navigation.setOptions({
      title: project.name,
      headerRight: () => (
        <TouchableOpacity
          style={styles.headerBtn}
          onPress={() =>
            navigation.navigate('CreateTask', {projectId: project.id, projectName: project.name})
          }>
          <Text style={styles.headerBtnText}>Add task</Text>
        </TouchableOpacity>
      ),
    });
  }, [navigation, project.id, project.name]);

  const treeQuery = useQuery({
    queryKey: ['mission-tree', project.id],
    queryFn: async (): Promise<TreePayload> => {
      try {
        const data = (await getMissionTree(project.id)) as TreePayload;
        return data;
      } catch {
        await syncEngine.init();
        const rows = await syncEngine.getTasksForProject(project.id);
        return {
          project: {name: project.name, goal: project.goal},
          tasks: {
            items: rows.map(r => ({
              id: r.id,
              title: r.title,
              description: r.description,
              status: r.status,
              assigned_to: r.assigned_to,
              updated_at: r.updated_at,
            })),
          },
        };
      }
    },
  });

  const items = treeQuery.data?.tasks?.items ?? [];
  const grouped = useMemo(() => groupTasks(items), [items]);

  const patchMutation = useMutation({
    mutationFn: ({taskId, status}: {taskId: string; status: string}) =>
      patchTaskStatus(taskId, status),
    onSuccess: () => qc.invalidateQueries({queryKey: ['mission-tree', project.id]}),
  });

  const onSwipeMove = useCallback(
    (task: MissionTask, delta: number) => {
      const next = moveStatus(task.status, delta);
      if (next !== task.status) {
        patchMutation.mutate({taskId: task.id, status: next});
      }
    },
    [patchMutation],
  );

  return (
    <View style={styles.root}>
      <Text style={styles.goal}>{treeQuery.data?.project?.goal ?? project.goal}</Text>
      <TouchableOpacity
        style={styles.treeLink}
        onPress={() => navigation.navigate('MissionTree', {projectId: project.id})}>
        <Text style={styles.treeLinkText}>Goal tree</Text>
      </TouchableOpacity>

      {treeQuery.isLoading ? (
        <ActivityIndicator style={styles.loader} />
      ) : (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.board}>
          {COLUMN_ORDER.map(key => (
            <View key={key} style={styles.column}>
              <Text style={styles.colTitle}>{COLUMN_LABEL[key]}</Text>
              <ScrollView style={styles.colScroll}>
                {grouped[key].map(task => (
                  <KanbanCard
                    key={task.id}
                    task={task}
                    onMove={d => onSwipeMove(task, d)}
                    onPress={() =>
                      navigation.navigate('TaskDetail', {projectId: project.id, task})
                    }
                  />
                ))}
              </ScrollView>
            </View>
          ))}
        </ScrollView>
      )}

      <Text style={styles.hint}>Swipe a card left or right to move it across columns.</Text>
    </View>
  );
}

function KanbanCard({
  task,
  onMove,
  onPress,
}: {
  task: MissionTask;
  onMove: (delta: number) => void;
  onPress: () => void;
}) {
  const panResponder = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_, g) =>
          Math.abs(g.dx) > 12 && Math.abs(g.dx) > Math.abs(g.dy),
        onPanResponderRelease: (_, g) => {
          if (g.dx > 44) {
            onMove(-1);
          } else if (g.dx < -44) {
            onMove(1);
          }
        },
      }),
    [onMove],
  );

  return (
    <Surface elevation={1} style={styles.card}>
      <View {...panResponder.panHandlers}>
        <TouchableOpacity onPress={onPress} activeOpacity={0.85}>
          <Text style={styles.cardTitle}>{task.title}</Text>
          {task.description ? (
            <Text numberOfLines={2} style={styles.cardDesc}>
              {task.description}
            </Text>
          ) : null}
        </TouchableOpacity>
      </View>
      <View style={styles.dots}>
        {COLUMN_ORDER.map(k => (
          <View
            key={k}
            style={[styles.dot, task.status === k ? styles.dotOn : styles.dotOff]}
          />
        ))}
      </View>
    </Surface>
  );
}

const styles = StyleSheet.create({
  root: {flex: 1, padding: 12, backgroundColor: '#09090b'},
  goal: {color: '#a1a1aa', marginBottom: 8},
  treeLink: {marginBottom: 12},
  treeLinkText: {color: '#818cf8', fontWeight: '600'},
  loader: {marginTop: 24},
  board: {paddingBottom: 12, gap: 12},
  column: {width: 260, marginRight: 12},
  colTitle: {fontWeight: '700', color: '#fafafa', marginBottom: 8},
  colScroll: {maxHeight: 420},
  card: {
    borderRadius: 10,
    padding: 12,
    marginBottom: 10,
    backgroundColor: '#18181b',
  },
  cardTitle: {color: '#fafafa', fontWeight: '600'},
  cardDesc: {color: '#a1a1aa', marginTop: 6, fontSize: 13},
  dots: {flexDirection: 'row', gap: 6, marginTop: 10},
  dot: {width: 8, height: 8, borderRadius: 4},
  dotOn: {backgroundColor: '#818cf8'},
  dotOff: {backgroundColor: '#3f3f46'},
  hint: {color: '#71717a', fontSize: 12, marginVertical: 10},
  headerBtn: {marginRight: 12},
  headerBtnText: {color: '#a5b4fc', fontWeight: '600'},
});
