import React, { useState, useContext } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../services/api';
import { AuthContext } from '../context/AuthContext';
import { Colors } from '../constants/Colors';

export default function LoginScreen() {
    const { idEmpresa, nombre } = useLocalSearchParams();
    const [usuarioStr, setUsuarioStr] = useState('');
    const [clave, setClave] = useState('');
    const [loading, setLoading] = useState(false);
    const { login } = useContext(AuthContext);
    const router = useRouter();

    const handleLogin = async () => {
        if (!usuarioStr) {
            Alert.alert('Error', 'Debe ingresar usuario');
            return;
        }

        setLoading(true);
        try {
            const response = await api.post('/login', {
                idEmpresa: idEmpresa,
                usuario: usuarioStr,
                clave: clave,
            });

            const { token, usuario } = response.data;
            await login(token, usuario, { idEmpresa, nombre });
            router.replace('/dashboard');
        } catch (error: any) {
            const msg = error.response?.data || 'Error conectando al servidor';
            Alert.alert('Credenciales incorrectas', typeof msg === 'string' ? msg : 'Error interno');
        } finally {
            setLoading(false);
        }
    };

    return (
        <View style={styles.container}>
            <Text style={styles.title}>Iniciar Sesión</Text>
            <Text style={styles.subtitle}>{nombre}</Text>

            <View style={styles.form}>
                <TextInput
                    style={styles.input}
                    placeholder="Usuario"
                    placeholderTextColor={Colors.light.textMuted}
                    value={usuarioStr}
                    onChangeText={setUsuarioStr}
                    autoCapitalize="none"
                />
                <TextInput
                    style={styles.input}
                    placeholder="Contraseña"
                    placeholderTextColor={Colors.light.textMuted}
                    value={clave}
                    onChangeText={setClave}
                    secureTextEntry
                />

                <TouchableOpacity
                    style={[styles.button, loading && styles.buttonDisabled]}
                    onPress={handleLogin}
                    disabled={loading}
                >
                    {loading ? (
                        <ActivityIndicator color="#FFF" />
                    ) : (
                        <Text style={styles.buttonText}>Ingresar</Text>
                    )}
                </TouchableOpacity>
            </View>
            <Text style={styles.version}>App CXP v1.0.0</Text>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.light.background,
        justifyContent: 'center',
        paddingHorizontal: 20,
    },
    title: {
        fontSize: 28,
        fontWeight: 'bold',
        color: Colors.light.text,
        textAlign: 'center',
        marginBottom: 5,
    },
    subtitle: {
        fontSize: 16,
        color: Colors.light.primary,
        textAlign: 'center',
        marginBottom: 40,
        fontWeight: '600',
    },
    form: {
        marginBottom: 20,
    },
    input: {
        backgroundColor: Colors.light.card,
        borderWidth: 1,
        borderColor: Colors.light.border,
        borderRadius: 8,
        padding: 15,
        fontSize: 16,
        marginBottom: 15,
        color: Colors.light.text,
    },
    button: {
        backgroundColor: Colors.light.primary,
        padding: 15,
        borderRadius: 8,
        alignItems: 'center',
    },
    buttonDisabled: {
        opacity: 0.7,
    },
    buttonText: {
        color: '#FFF',
        fontSize: 16,
        fontWeight: 'bold',
    },
    version: {
        textAlign: 'center',
        color: Colors.light.textMuted,
        marginTop: 20,
        fontSize: 12,
    }
});
