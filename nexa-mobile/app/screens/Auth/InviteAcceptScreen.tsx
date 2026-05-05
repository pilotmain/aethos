import React, {useState} from 'react';
import {Alert, StyleSheet, Text, View} from 'react-native';

import {Button} from '../../components/common/Button';
import {Input} from '../../components/common/Input';

/** Accept flow is Telegram-first today; this screen reserves UX for deep links. */
export default function InviteAcceptScreen() {
  const [code, setCode] = useState('');
  return (
    <View style={styles.c}>
      <Text style={styles.t}>Paste invite code</Text>
      <Input value={code} onChangeText={setCode} placeholder="invite id" />
      <Button
        title="Accept (coming soon)"
        onPress={() => Alert.alert('Use /org join on Telegram', code || '(empty)')}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  c: {flex: 1, padding: 16},
  t: {marginBottom: 12},
});
