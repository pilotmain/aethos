import React from 'react';
import {ScrollView, StyleSheet} from 'react-native';
import {Text} from 'react-native-paper';

/** Placeholder — align limits with web workspace settings when mobile PATCH endpoints ship. */
export default function BudgetSettingsScreen() {
  return (
    <ScrollView contentContainerStyle={styles.c}>
      <Text variant="titleMedium">Budget limits</Text>
      <Text variant="bodyMedium" style={styles.body}>
        Configure org-wide token budgets in the AethOS web app for now. Mobile will mirror alerts once limit APIs are
        exposed for JWT clients.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  c: {padding: 16, backgroundColor: '#09090b'},
  body: {marginTop: 12, color: '#a1a1aa'},
});
