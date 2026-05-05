import React, {useEffect, useState} from 'react';
import {ScrollView, StyleSheet, Text} from 'react-native';

import {budgetSummary} from '../../services/api/budget';
import {useWorkspaceStore} from '../../store/workspaceStore';

export default function BudgetScreen() {
  const orgId = useWorkspaceStore(s => s.activeOrgId);
  const [note, setNote] = useState('');

  useEffect(() => {
    void (async () => {
      if (!orgId) {
        return;
      }
      const b = await budgetSummary(orgId);
      setNote(String(b.note ?? JSON.stringify(b)));
    })();
  }, [orgId]);

  return (
    <ScrollView contentContainerStyle={styles.c}>
      <Text style={styles.h}>Budget</Text>
      <Text style={styles.body}>{note || 'Select a workspace.'}</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  c: {padding: 16},
  h: {fontSize: 20, fontWeight: '700', marginBottom: 12},
  body: {color: '#374151'},
});
