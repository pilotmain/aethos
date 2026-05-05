import React, {useEffect, useState} from 'react';
import {FlatList, StyleSheet, Text, TouchableOpacity, View} from 'react-native';

import {listOrgs, setActiveOrg} from '../../services/api/orgs';
import type {OrgSummary} from '../../types';
import {useWorkspaceStore} from '../../store/workspaceStore';

export default function WorkspaceSelectScreen() {
  const [orgs, setOrgs] = useState<OrgSummary[]>([]);
  const setActiveOrgId = useWorkspaceStore(s => s.setActiveOrgId);

  useEffect(() => {
    void (async () => {
      const data = await listOrgs();
      setOrgs(data.organizations);
      if (data.active_organization_id) {
        setActiveOrgId(data.active_organization_id);
      }
    })();
  }, [setActiveOrgId]);

  const pick = async (id: string) => {
    await setActiveOrg(id);
    setActiveOrgId(id);
  };

  return (
    <View style={styles.container}>
      <Text style={styles.h}>Workspaces</Text>
      <FlatList
        data={orgs}
        keyExtractor={o => o.id}
        renderItem={({item}) => (
          <TouchableOpacity style={styles.row} onPress={() => void pick(item.id)}>
            <Text style={styles.name}>{item.name}</Text>
            <Text style={styles.slug}>{item.slug}</Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, padding: 16},
  h: {fontSize: 20, fontWeight: '600', marginBottom: 12},
  row: {
    padding: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderColor: '#e5e7eb',
  },
  name: {fontSize: 16, fontWeight: '600'},
  slug: {color: '#6b7280', marginTop: 4},
});
