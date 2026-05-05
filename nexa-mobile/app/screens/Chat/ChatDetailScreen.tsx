import React, {useEffect, useRef, useState} from 'react';
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
  Text,
} from 'react-native';
import type {StackScreenProps} from '@react-navigation/stack';

import {MessageBubble} from '../../components/chat/MessageBubble';
import type {ChatStackParamList} from '../../navigation/types';
import {connectMobileChatWebSocket} from '../../services/websocket';
import {useAuthStore} from '../../store/authStore';
import {useChatStore} from '../../store/chatStore';
import type {ChatMessage} from '../../types';

type Props = StackScreenProps<ChatStackParamList, 'ChatDetail'>;

export default function ChatDetailScreen(_props: Props) {
  const token = useAuthStore(s => s.token);
  const messages = useChatStore(s => s.messages);
  const pushMessage = useChatStore(s => s.pushMessage);
  const clear = useChatStore(s => s.clear);
  const [input, setInput] = useState('');
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    clear();
    const conn = connectMobileChatWebSocket(token, msg => {
      if (msg.type === 'ready') {
        pushMessage({
          id: 'ready',
          text: 'Connected to Nexa mobile channel.',
          isUser: false,
          createdAt: new Date(),
        });
      }
      if (msg.type === 'message') {
        pushMessage({
          id: `${Date.now()}-srv`,
          text: typeof msg.echo === 'object' ? JSON.stringify(msg.echo) : String(msg.echo ?? ''),
          isUser: false,
          createdAt: new Date(),
        });
      }
    });
    wsRef.current = conn?.ws ?? null;
    return () => conn?.close();
  }, [token, clear, pushMessage]);

  const send = () => {
    const t = input.trim();
    if (!t || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }
    pushMessage({id: `${Date.now()}-u`, text: t, isUser: true, createdAt: new Date()});
    wsRef.current.send(JSON.stringify({text: t}));
    setInput('');
  };

  const renderItem = ({item}: {item: ChatMessage}) => (
    <MessageBubble text={item.text} isUser={item.isUser} />
  );

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <FlatList data={messages} renderItem={renderItem} keyExtractor={m => m.id} contentContainerStyle={styles.list} />
      <View style={styles.row}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder="Message Nexa…"
        />
        <TouchableOpacity onPress={send} style={styles.send}>
          <Text style={styles.sendT}>Send</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: {flex: 1},
  list: {padding: 12},
  row: {flexDirection: 'row', padding: 10, alignItems: 'center'},
  input: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  send: {marginLeft: 8, paddingHorizontal: 14, paddingVertical: 10},
  sendT: {color: '#2563eb', fontWeight: '700'},
});
