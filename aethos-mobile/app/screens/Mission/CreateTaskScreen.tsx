import {useMutation, useQueryClient} from '@tanstack/react-query';
import React, {useLayoutEffect, useState} from 'react';
import {Alert, ScrollView, StyleSheet, View} from 'react-native';
import {TextInput} from 'react-native-paper';
import type {StackScreenProps} from '@react-navigation/stack';

import {Button} from '../../components/common/Button';
import type {MissionStackParamList} from '../../navigation/types';
import {createTask} from '../../services/api/tasks';

type Props = StackScreenProps<MissionStackParamList, 'CreateTask'>;

export default function CreateTaskScreen({route, navigation}: Props) {
  const {projectId, projectName} = route.params;
  const qc = useQueryClient();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');

  useLayoutEffect(() => {
    navigation.setOptions({title: `New task · ${projectName}`});
  }, [navigation, projectName]);

  const mutation = useMutation({
    mutationFn: () =>
      createTask({
        title: title.trim(),
        project_id: projectId,
        description: description.trim() || null,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({queryKey: ['mission-tree', projectId]});
      navigation.goBack();
    },
    onError: (e: unknown) => {
      const msg = e instanceof Error ? e.message : 'Could not create task';
      Alert.alert('Error', msg);
    },
  });

  const submit = () => {
    if (!title.trim()) {
      Alert.alert('Title required', 'Enter a task title.');
      return;
    }
    mutation.mutate();
  };

  return (
    <ScrollView contentContainerStyle={styles.c} keyboardShouldPersistTaps="handled">
      <TextInput
        mode="outlined"
        label="Title"
        value={title}
        onChangeText={setTitle}
        style={styles.input}
      />
      <TextInput
        mode="outlined"
        label="Description (optional)"
        value={description}
        onChangeText={setDescription}
        multiline
        style={styles.input}
      />
      <View style={styles.actions}>
        <Button title={mutation.isPending ? 'Creating…' : 'Create'} onPress={submit} disabled={mutation.isPending} />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  c: {padding: 16, backgroundColor: '#09090b'},
  input: {marginBottom: 12, backgroundColor: '#18181b'},
  actions: {marginTop: 8},
});
