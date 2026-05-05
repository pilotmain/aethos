import React, {useCallback, useEffect, useLayoutEffect, useState} from 'react';
import {FlatList, StyleSheet, Text, TouchableOpacity, View} from 'react-native';
import type {StackScreenProps} from '@react-navigation/stack';

import {listOrgMembers} from '../../services/api/orgs';
import {placeholderTeamNotice} from '../../services/api/team';
import type {TeamStackParamList} from '../../navigation/types';
import {useWorkspaceStore} from '../../store/workspaceStore';

type Props = StackScreenProps<TeamStackParamList, 'TeamHome'>;

export default function TeamScreen({navigation}: Props) {
  const orgId = useWorkspaceStore(s => s.activeOrgId);
  const [members, setMembers] = useState<{user_id: string; role: string; user_name?: string | null}[]>([]);

  useLayoutEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <TouchableOpacity style={styles.invite} onPress={() => navigation.navigate('Invite')}>
          <Text style={styles.inviteT}>Invite</Text>
        </TouchableOpacity>
      ),
    });
  }, [navigation]);

  const load = useCallback(async () => {
    if (!orgId) {
      return;
    }
    const data = await listOrgMembers(orgId);
    setMembers(data.members);
    await placeholderTeamNotice();
  }, [orgId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!orgId) {
    return (
      <View style={styles.c}>
        <Text style={styles.warn}>Select a workspace first.</Text>
      </View>
    );
  }

  return (
    <View style={styles.c}>
      <FlatList
        data={members}
        keyExtractor={m => m.user_id}
        refreshing={false}
        onRefresh={() => void load()}
        renderItem={({item}) => (
          <TouchableOpacity
            style={styles.row}
            onPress={() =>
              navigation.navigate('MemberDetail', {
                member: {
                  user_id: item.user_id,
                  user_name: item.user_name,
                  role: item.role,
                },
              })
            }>
            <Text style={styles.n}>{item.user_name || item.user_id}</Text>
            <Text style={styles.r}>{item.role}</Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  c: {flex: 1, padding: 16, backgroundColor: '#09090b'},
  warn: {color: '#fbbf24'},
  row: {
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: '#27272a',
  },
  n: {fontWeight: '600', color: '#fafafa'},
  r: {color: '#a1a1aa', marginTop: 4},
  invite: {marginRight: 12},
  inviteT: {color: '#a5b4fc', fontWeight: '600'},
});
