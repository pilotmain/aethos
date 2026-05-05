import React from 'react';
import {ScrollView, StyleSheet, Text} from 'react-native';

/** Renders mission tree JSON from GET /mobile/projects/:id/tree */
export function GoalTree({payload}: {payload: Record<string, unknown> | null}) {
  if (!payload) {
    return <Text style={styles.muted}>No tree loaded.</Text>;
  }
  return (
    <ScrollView style={styles.box}>
      <Text selectable>{JSON.stringify(payload, null, 2)}</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  box: {maxHeight: 320, backgroundColor: '#f9fafb', padding: 8, borderRadius: 8},
  muted: {color: '#6b7280'},
});
