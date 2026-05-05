import React from 'react';
import {StyleSheet, Text, TouchableOpacity, View} from 'react-native';
import type {StackScreenProps} from '@react-navigation/stack';

import type {ChatStackParamList} from '../../navigation/types';

type Props = StackScreenProps<ChatStackParamList, 'ChatList'>;

export default function ChatListScreen({navigation}: Props) {
  return (
    <View style={styles.c}>
      <Text style={styles.t}>Nexa chat session</Text>
      <TouchableOpacity style={styles.btn} onPress={() => navigation.navigate('ChatDetail')}>
        <Text style={styles.btnT}>Open conversation</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  c: {flex: 1, padding: 16, justifyContent: 'center'},
  t: {textAlign: 'center', marginBottom: 12},
  btn: {backgroundColor: '#2563eb', padding: 14, borderRadius: 10, alignItems: 'center'},
  btnT: {color: '#fff', fontWeight: '600'},
});
