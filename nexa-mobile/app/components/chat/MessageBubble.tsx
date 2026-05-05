import React from 'react';
import {StyleSheet, Text, View} from 'react-native';

type Props = {text: string; isUser: boolean};

export function MessageBubble({text, isUser}: Props) {
  return (
    <View style={[styles.wrap, isUser ? styles.user : styles.bot]}>
      <Text style={styles.text}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    maxWidth: '85%',
    padding: 10,
    borderRadius: 14,
    marginVertical: 4,
  },
  user: {alignSelf: 'flex-end', backgroundColor: '#dbeafe'},
  bot: {alignSelf: 'flex-start', backgroundColor: '#f3f4f6'},
  text: {fontSize: 15},
});
