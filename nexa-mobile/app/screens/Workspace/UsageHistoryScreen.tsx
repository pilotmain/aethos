import {useQuery} from '@tanstack/react-query';
import React from 'react';
import {ScrollView, StyleSheet, View} from 'react-native';
import {ActivityIndicator, Card, Text} from 'react-native-paper';

import {fetchDashboard} from '../../services/api/mobile';

export default function UsageHistoryScreen() {
  const q = useQuery({
    queryKey: ['dashboard-metrics-usage'],
    queryFn: fetchDashboard,
  });

  return (
    <ScrollView contentContainerStyle={styles.c}>
      <Text variant="titleMedium">Usage snapshot</Text>
      <Text variant="bodySmall" style={styles.sub}>
        Detailed provider usage rolls up from the same metrics as the dashboard until dedicated usage series land on
        mobile.
      </Text>
      {q.isLoading ? (
        <ActivityIndicator style={styles.loader} />
      ) : q.data ? (
        <Card mode="elevated" style={styles.card}>
          <Card.Content>
            <Row label="Budget %" value={`${q.data.budget_percentage}%`} />
            <Row label="Budget used" value={String(q.data.budget_used)} />
            <Row label="Budget limit" value={String(q.data.budget_limit)} />
            <Row label="Tasks (total)" value={String(q.data.total_tasks)} />
            <Row label="In progress" value={String(q.data.in_progress_tasks)} />
          </Card.Content>
        </Card>
      ) : (
        <Text style={styles.muted}>Offline or unavailable.</Text>
      )}
    </ScrollView>
  );
}

function Row({label, value}: {label: string; value: string}) {
  return (
    <View style={styles.row}>
      <Text style={styles.muted}>{label}</Text>
      <Text variant="bodyLarge">{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  c: {padding: 16, backgroundColor: '#09090b'},
  sub: {color: '#71717a', marginTop: 8, marginBottom: 16},
  loader: {marginTop: 16},
  card: {backgroundColor: '#18181b'},
  row: {marginBottom: 12},
  muted: {color: '#a1a1aa'},
});
