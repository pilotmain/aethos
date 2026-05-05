import React from 'react';
import {ActivityIndicator, View} from 'react-native';

export function Loading() {
  return (
    <View style={{padding: 24}}>
      <ActivityIndicator size="large" />
    </View>
  );
}
