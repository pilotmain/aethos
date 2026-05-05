import React from 'react';
import {StyleSheet, Text, View} from 'react-native';

export default function InviteScreen() {
  return (
    <View style={styles.c}>
      <Text style={styles.t}>Create invites from Telegram (/org invite) or wire POST /mobile/invite later.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  c: {flex: 1, padding: 16},
  t: {color: '#374151'},
});
