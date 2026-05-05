import React from 'react';
import {StyleSheet, Text} from 'react-native';

export default function MemberDetailScreen() {
  return <Text style={styles.t}>Member detail — extend with RBAC APIs.</Text>;
}

const styles = StyleSheet.create({
  t: {padding: 16},
});
