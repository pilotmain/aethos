import {useQuery} from '@tanstack/react-query';
import React from 'react';
import {ScrollView, StyleSheet} from 'react-native';
import {Card, ProgressBar, Text} from 'react-native-paper';

import {budgetSummary} from '../../services/api/budget';
import {fetchDashboard} from '../../services/api/mobile';
import {useWorkspaceStore} from '../../store/workspaceStore';

export default function BudgetScreen() {
  const orgId = useWorkspaceStore(s => s.activeOrgId);

  const dash = useQuery({
    queryKey: ['dashboard-metrics-budget'],
    queryFn: fetchDashboard,
    enabled: !!orgId,
  });

  const note = useQuery({
    queryKey: ['budget-note', orgId],
    queryFn: async () => {
      if (!orgId) {
        return '';
      }
      const b = await budgetSummary(orgId);
      return String(b.note ?? '');
    },
    enabled: !!orgId,
  });

  if (!orgId) {
    return (
      <ScrollView contentContainerStyle={styles.c}>
        <Text style={styles.muted}>Select a workspace.</Text>
      </ScrollView>
    );
  }

  const pct = dash.data?.budget_percentage ?? 0;

  return (
    <ScrollView contentContainerStyle={styles.c}>
      <Text variant="titleLarge" style={styles.h}>
        Budget
      </Text>
      <Card mode="elevated" style={styles.card}>
        <Card.Content>
          <Text variant="titleMedium">Workspace usage</Text>
          <Text variant="bodySmall" style={styles.muted}>
            {dash.data?.budget_used ?? 0} / {dash.data?.budget_limit || '—'} tokens (placeholder)
          </Text>
          <ProgressBar progress={Math.min(1, pct / 100)} style={styles.bar} />
        </Card.Content>
      </Card>
      <Card mode="elevated" style={styles.card}>
        <Card.Content>
          <Text variant="bodyMedium" style={styles.note}>
            {note.data || 'Loading note…'}
          </Text>
        </Card.Content>
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  c: {padding: 16, backgroundColor: '#09090b'},
  h: {marginBottom: 12, color: '#fafafa'},
  card: {marginBottom: 12, backgroundColor: '#18181b'},
  muted: {color: '#a1a1aa', marginTop: 8},
  bar: {marginTop: 12, height: 8, borderRadius: 4},
  note: {color: '#a1a1aa'},
});
