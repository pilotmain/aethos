import React from 'react';
import {StyleSheet, Text, View} from 'react-native';
import type {StackScreenProps} from '@react-navigation/stack';

import {Button} from '../../components/common/Button';
import type {MissionStackParamList} from '../../navigation/types';

type Props = StackScreenProps<MissionStackParamList, 'ProjectDetail'>;

export default function ProjectDetailScreen({route, navigation}: Props) {
  const {project} = route.params;
  return (
    <View style={styles.c}>
      <Text style={styles.h}>{project.name}</Text>
      <Text style={styles.g}>{project.goal}</Text>
      <Button title="Open mission tree" onPress={() => navigation.navigate('MissionTree', {projectId: project.id})} />
    </View>
  );
}

const styles = StyleSheet.create({
  c: {flex: 1, padding: 16},
  h: {fontSize: 22, fontWeight: '700'},
  g: {marginTop: 12, color: '#374151'},
});
