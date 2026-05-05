import React from 'react';
import {StyleSheet, Text, View} from 'react-native';

export function ProgressBar({progress}: {progress: number}) {
  const pct = Math.max(0, Math.min(100, progress));
  return (
    <View>
      <View style={styles.track}>
        <View style={[styles.fill, {width: `${pct}%`}]} />
      </View>
      <Text style={styles.label}>{pct}%</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    height: 8,
    backgroundColor: '#e5e7eb',
    borderRadius: 4,
    overflow: 'hidden',
  },
  fill: {height: '100%', backgroundColor: '#22c55e'},
  label: {marginTop: 4, fontSize: 12, color: '#6b7280'},
});
