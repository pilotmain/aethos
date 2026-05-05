import React from 'react';
import {StyleSheet, Text} from 'react-native';

export function TypingIndicator() {
  return <Text style={styles.t}>AethOS is typing…</Text>;
}

const styles = StyleSheet.create({
  t: {fontStyle: 'italic', color: '#6b7280', marginLeft: 8},
});
