import React from 'react';
import {StyleSheet, Text, TouchableOpacity} from 'react-native';

type Props = {title: string; onPress: () => void; disabled?: boolean};

export function Button({title, onPress, disabled}: Props) {
  return (
    <TouchableOpacity style={[styles.btn, disabled && styles.disabled]} onPress={onPress} disabled={disabled}>
      <Text style={styles.text}>{title}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  btn: {
    backgroundColor: '#2563eb',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 10,
    alignItems: 'center',
  },
  disabled: {opacity: 0.5},
  text: {color: '#fff', fontWeight: '600'},
});
