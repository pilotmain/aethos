import React from 'react';
import {StyleSheet, Text} from 'react-native';
import type {StackScreenProps} from '@react-navigation/stack';

import type {MissionStackParamList} from '../../navigation/types';

type Props = StackScreenProps<MissionStackParamList, 'TaskDetail'>;

export default function TaskDetailScreen(_props: Props) {
  return <Text style={styles.t}>Task detail — extend with PATCH APIs when added.</Text>;
}

const styles = StyleSheet.create({
  t: {padding: 16},
});
