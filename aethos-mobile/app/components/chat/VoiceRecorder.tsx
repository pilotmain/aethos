import React from 'react';
import {StyleSheet, Text, View} from 'react-native';

/** Placeholder — wire react-native-audio-recorder-player when enabling voice UX. */
export function VoiceRecorder() {
  return (
    <View style={styles.box}>
      <Text style={styles.t}>Voice recording not wired in this build.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  box: {padding: 8},
  t: {color: '#6b7280'},
});
