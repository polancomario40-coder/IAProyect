import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Colors } from '../constants/Colors';

export default function ConfirmacionScreen() {
    const { idDocumento } = useLocalSearchParams();
    const router = useRouter();

    return (
        <View style={styles.container}>
            <View style={styles.iconContainer}>
                <Text style={styles.checkIcon}>✅</Text>
            </View>

            <Text style={styles.title}>Factura Registrada</Text>
            <Text style={styles.subtitle}>La factura se ha guardado correctamente en el ERP.</Text>

            <View style={styles.idBox}>
                <Text style={styles.idLabel}>ID Documento</Text>
                <Text style={styles.idValue}>{idDocumento}</Text>
            </View>

            <TouchableOpacity style={styles.button} onPress={() => router.replace('/dashboard')}>
                <Text style={styles.buttonText}>Volver al Dashboard</Text>
            </TouchableOpacity>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.light.background,
        justifyContent: 'center',
        alignItems: 'center',
        padding: 20,
    },
    iconContainer: {
        backgroundColor: Colors.light.success + '20', // slight opacity
        width: 100,
        height: 100,
        borderRadius: 50,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: 20,
    },
    checkIcon: {
        fontSize: 50,
    },
    title: {
        fontSize: 26,
        fontWeight: 'bold',
        color: Colors.light.text,
        marginBottom: 10,
    },
    subtitle: {
        fontSize: 16,
        color: Colors.light.textMuted,
        textAlign: 'center',
        marginBottom: 30,
    },
    idBox: {
        backgroundColor: Colors.light.card,
        padding: 20,
        borderRadius: 8,
        borderWidth: 1,
        borderColor: Colors.light.border,
        alignItems: 'center',
        width: '100%',
        marginBottom: 40,
    },
    idLabel: {
        fontSize: 14,
        color: Colors.light.textMuted,
        marginBottom: 5,
    },
    idValue: {
        fontSize: 24,
        fontWeight: 'bold',
        color: Colors.light.primary,
    },
    button: {
        backgroundColor: Colors.light.primary,
        padding: 16,
        borderRadius: 8,
        alignItems: 'center',
        width: '100%',
    },
    buttonText: {
        color: '#FFF',
        fontSize: 18,
        fontWeight: 'bold',
    }
});
