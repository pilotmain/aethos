import React from 'react';
import {StyleSheet, Text} from 'react-native';

export default function UsageScreen() {
  return (
    <Text style={styles.t}>
      Usage mirrors Phase 28 token economy — connect providers_usage or budget detail endpoints when exposed for mobile.
    </Text>
  );
}

const styles = StyleSheet.create({
  t: {padding: 16, color: '#4b5563'},
});
