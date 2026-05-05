import React from 'react';
import {ScrollView, StyleSheet} from 'react-native';
import {Card, Text} from 'react-native-paper';
import type {StackScreenProps} from '@react-navigation/stack';

import type {TeamStackParamList} from '../../navigation/types';

type Props = StackScreenProps<TeamStackParamList, 'MemberDetail'>;

export default function MemberDetailScreen({route}: Props) {
  const {member} = route.params;
  return (
    <ScrollView contentContainerStyle={styles.c}>
      <Card mode="elevated" style={styles.card}>
        <Card.Content>
          <Text variant="headlineSmall">{member.user_name || member.user_id}</Text>
          <Text variant="bodyMedium" style={styles.meta}>
            User id: {member.user_id}
          </Text>
          <Text variant="titleMedium" style={styles.role}>
            Role: {member.role}
          </Text>
          <Text variant="bodySmall" style={styles.note}>
            Usage and assignment drill-down can mirror web RBAC when member-scoped metrics are exposed for mobile JWT.
          </Text>
        </Card.Content>
      </Card>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  c: {padding: 16, backgroundColor: '#09090b'},
  card: {backgroundColor: '#18181b'},
  meta: {color: '#a1a1aa', marginTop: 8},
  role: {marginTop: 16, color: '#fafafa'},
  note: {color: '#71717a', marginTop: 16},
});
