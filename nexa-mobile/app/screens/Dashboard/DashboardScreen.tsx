import {useQuery} from '@tanstack/react-query';
import React from 'react';
import {RefreshControl, ScrollView, StyleSheet, View} from 'react-native';
import {ActivityIndicator, Card, ProgressBar, Text} from 'react-native-paper';

import {fetchDashboard} from '../../services/api/mobile';
import {syncEngine} from '../../services/offline/sync-engine';
import {useWorkspaceStore} from '../../store/workspaceStore';

export default function DashboardScreen() {
  const activeOrgId = useWorkspaceStore(s => s.activeOrgId);

  const q = useQuery({
    queryKey: ['dashboard-metrics', activeOrgId],
    queryFn: async () => {
      try {
        return await fetchDashboard();
      } catch {
        await syncEngine.init();
        const projects = await syncEngine.getProjects();
        return {
          active_projects: projects.filter(p => p.status === 'active').length,
          team_members: 0,
          total_tasks: 0,
          in_progress_tasks: 0,
          budget_used: 0,
          budget_limit: 0,
          budget_percentage: 0,
          recent_tasks: [],
          active_organization_id: activeOrgId,
        };
      }
    },
  });

  const m = q.data;

  return (
    <ScrollView
      contentContainerStyle={styles.c}
      refreshControl={<RefreshControl refreshing={q.isFetching} onRefresh={() => void q.refetch()} />}>
      <Text variant="headlineSmall" style={styles.h}>
        Overview
      </Text>

      {q.isLoading ? (
        <ActivityIndicator style={styles.loader} />
      ) : m ? (
        <>
          <View style={styles.row}>
            <Card mode="elevated" style={styles.cardHalf}>
              <Card.Content>
                <Text variant="labelMedium">Projects</Text>
                <Text variant="headlineMedium">{m.active_projects}</Text>
              </Card.Content>
            </Card>
            <Card mode="elevated" style={styles.cardHalf}>
              <Card.Content>
                <Text variant="labelMedium">Team</Text>
                <Text variant="headlineMedium">{m.team_members}</Text>
              </Card.Content>
            </Card>
          </View>

          <Card mode="elevated" style={styles.card}>
            <Card.Content>
              <Text variant="titleMedium">Tasks</Text>
              <Text variant="bodyMedium" style={styles.muted}>
                Total {m.total_tasks} · In progress {m.in_progress_tasks}
              </Text>
            </Card.Content>
          </Card>

          <Card mode="elevated" style={styles.card}>
            <Card.Content>
              <Text variant="titleMedium">Budget usage</Text>
              <Text variant="bodySmall" style={styles.muted}>
                {m.budget_used} / {m.budget_limit || '—'} tokens (placeholder until linked budgets)
              </Text>
              <ProgressBar progress={Math.min(1, (m.budget_percentage || 0) / 100)} style={styles.bar} />
            </Card.Content>
          </Card>

          <Card mode="elevated" style={styles.card}>
            <Card.Content>
              <Text variant="titleMedium">Recent tasks</Text>
              {m.recent_tasks.length === 0 ? (
                <Text style={styles.muted}>No tasks yet.</Text>
              ) : (
                m.recent_tasks.map(t => (
                  <View key={t.id} style={styles.taskRow}>
                    <Text variant="bodyLarge">{t.title}</Text>
                    <Text variant="bodySmall" style={styles.muted}>
                      {t.status}
                    </Text>
                  </View>
                ))
              )}
            </Card.Content>
          </Card>
        </>
      ) : (
        <Text style={styles.muted}>Could not load metrics.</Text>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  c: {padding: 16, paddingBottom: 32, backgroundColor: '#09090b'},
  h: {marginBottom: 16, color: '#fafafa'},
  loader: {marginTop: 24},
  row: {flexDirection: 'row', gap: 12, marginBottom: 12},
  cardHalf: {flex: 1, backgroundColor: '#18181b'},
  card: {marginBottom: 12, backgroundColor: '#18181b'},
  muted: {color: '#a1a1aa', marginTop: 4},
  bar: {marginTop: 12, height: 8, borderRadius: 4},
  taskRow: {marginTop: 12},
});
