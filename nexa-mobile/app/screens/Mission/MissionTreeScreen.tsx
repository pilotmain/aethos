import React, {useEffect, useState} from 'react';
import {StyleSheet, View} from 'react-native';
import type {StackScreenProps} from '@react-navigation/stack';

import {GoalTree} from '../../components/mission/GoalTree';
import {Loading} from '../../components/common/Loading';
import type {MissionStackParamList} from '../../navigation/types';
import {getMissionTree} from '../../services/api/projects';

type Props = StackScreenProps<MissionStackParamList, 'MissionTree'>;

export default function MissionTreeScreen({route}: Props) {
  const {projectId} = route.params;
  const [tree, setTree] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      setLoading(true);
      try {
        const t = await getMissionTree(projectId);
        setTree(t);
      } finally {
        setLoading(false);
      }
    })();
  }, [projectId]);

  if (loading) {
    return <Loading />;
  }

  return (
    <View style={styles.c}>
      <GoalTree payload={tree} />
    </View>
  );
}

const styles = StyleSheet.create({
  c: {flex: 1, padding: 12},
});
