import React, {useEffect, useState} from 'react';
import {FlatList, StyleSheet, Text, View} from 'react-native';

import {listOrgMembers} from '../../services/api/orgs';
import {placeholderTeamNotice} from '../../services/api/team';
import {useWorkspaceStore} from '../../store/workspaceStore';

export default function TeamScreen() {
  const orgId = useWorkspaceStore(s => s.activeOrgId);
  const [members, setMembers] = useState<{user_id: string; role: string; user_name?: string}[]>([]);

  useEffect(() => {
    void (async () => {
      if (!orgId) {
        return;
      }
      const data = await listOrgMembers(orgId);
      setMembers(data.members);
      await placeholderTeamNotice();
    })();
  }, [orgId]);

  if (!orgId) {
    return (
      <View style={styles.c}>
        <Text>Select a workspace first.</Text>
      </View>
    );
  }

  return (
    <View style={styles.c}>
      <Text style={styles.h}>Members</Text>
      <FlatList
        data={members}
        keyExtractor={m => m.user_id}
        renderItem={({item}) => (
          <View style={styles.row}>
            <Text style={styles.n}>{item.user_name || item.user_id}</Text>
            <Text style={styles.r}>{item.role}</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  c: {flex: 1, padding: 16},
  h: {fontSize: 20, fontWeight: '700', marginBottom: 12},
  row: {
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: '#e5e7eb',
  },
  n: {fontWeight: '600'},
  r: {color: '#6b7280', marginTop: 4},
});
