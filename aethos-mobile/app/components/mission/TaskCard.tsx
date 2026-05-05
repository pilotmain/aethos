import React from 'react';
import {StyleSheet, Text, View} from 'react-native';

type Props = {title: string; subtitle?: string};

export function TaskCard({title, subtitle}: Props) {
  return (
    <View style={styles.row}>
      <Text style={styles.title}>{title}</Text>
      {subtitle ? <Text style={styles.sub}>{subtitle}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {paddingVertical: 8},
  title: {fontWeight: '600'},
  sub: {color: '#6b7280', marginTop: 4},
});
