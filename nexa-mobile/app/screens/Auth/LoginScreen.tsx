import React, {useState} from 'react';
import {Alert, StyleSheet, Text, View} from 'react-native';

import {Button} from '../../components/common/Button';
import {Input} from '../../components/common/Input';
import {loginMobile} from '../../services/api/auth';
import {listOrgs, setActiveOrg} from '../../services/api/orgs';
import {useAuthStore} from '../../store/authStore';
import {useWorkspaceStore} from '../../store/workspaceStore';

export default function LoginScreen() {
  const [userId, setUserId] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const setSession = useAuthStore(s => s.setSession);
  const setActiveOrgId = useWorkspaceStore(s => s.setActiveOrgId);

  const onLogin = async () => {
    const uid = userId.trim();
    if (!uid) {
      Alert.alert('User id required', 'Use the same id as your Nexa account (e.g. Telegram numeric id).');
      return;
    }
    setBusy(true);
    try {
      const res = await loginMobile(uid, name.trim() || undefined);
      setSession(res.token, res.user.id, res.user.name ?? null, res.organizations);
      const orgs = await listOrgs();
      const active = orgs.active_organization_id ?? orgs.organizations[0]?.id ?? null;
      if (active) {
        await setActiveOrg(active);
        setActiveOrgId(active);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Login failed';
      Alert.alert('Login error', msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.h1}>Nexa</Text>
      <Text style={styles.sub}>Mission Control & agents</Text>
      <Input placeholder="User id" value={userId} onChangeText={setUserId} />
      <Input placeholder="Display name (optional)" value={name} onChangeText={setName} />
      <Button title={busy ? 'Signing in…' : 'Continue'} onPress={onLogin} disabled={busy} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, padding: 20, justifyContent: 'center'},
  h1: {fontSize: 28, fontWeight: '700', marginBottom: 4},
  sub: {color: '#6b7280', marginBottom: 20},
});
