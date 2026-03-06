import React from 'react';
import { View, ActivityIndicator } from 'react-native';
import { Colors } from '../constants/Colors';

export default function IndexScreen() {
    return (
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: Colors.light.background }}>
            <ActivityIndicator size="large" color="#1F3A8A" />
        </View>
    );
}
