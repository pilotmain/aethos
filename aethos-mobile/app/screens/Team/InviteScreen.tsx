import React from 'react';
import {ScrollView, StyleSheet} from 'react-native';
import {Text} from 'react-native-paper';

export default function InviteScreen() {
  return (
    <ScrollView contentContainerStyle={styles.c}>
      <Text variant="bodyMedium" style={styles.t}>
        Invites are issued from the AethOS Telegram bot (`/org invite`) or the web console today. A dedicated mobile
        invite API can register tokens here later.
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  c: {padding: 16, backgroundColor: '#09090b'},
  t: {color: '#a1a1aa'},
});
