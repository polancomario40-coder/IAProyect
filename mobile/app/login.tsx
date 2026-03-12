import React, { useState, useContext } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, ActivityIndicator, SafeAreaView, KeyboardAvoidingView, Platform, Dimensions, Image } from 'react-native';
import { useRouter } from 'expo-router';
import api from '../services/api';
import { AuthContext } from '../context/AuthContext';
import { Colors } from '../constants/Colors';

const { width } = Dimensions.get('window');

export default function LoginScreen() {
    const [usuarioStr, setUsuarioStr] = useState('');
    const [clave, setClave] = useState('');
    const [loading, setLoading] = useState(false);
    const { login } = useContext(AuthContext);
    const router = useRouter();

    const handleLogin = async () => {
        if (!usuarioStr) {
            Alert.alert('Error', 'Debe ingresar el usuario');
            return;
        }

        setLoading(true);
        try {
            const response = await api.post('/login', {
                usuario: usuarioStr,
                clave: clave,
            });

            const { token, usuario } = response.data;
            await login(token, usuario);
        } catch (error: any) {
            const msg = error.response?.data || 'Error conectando al servidor';
            Alert.alert('Credenciales incorrectas', typeof msg === 'string' ? msg : 'Error interno');
        } finally {
            setLoading(false);
        }
    };

    return (
        <SafeAreaView style={styles.safeArea}>
            <KeyboardAvoidingView
                behavior={Platform.OS === 'ios' ? 'padding' : undefined}
                style={styles.keyboardView}
            >
                <View style={styles.container}>
                    <View style={styles.logoContainer}>
                        <Image 
                            source={require('../assets/images/logo-sade.png')} 
                            style={styles.logo}
                            resizeMode="contain"
                        />
                    </View>
                    <Text style={styles.title}>CXPay Pro</Text>
                    <Text style={styles.subtitle}>Iniciar Sesión</Text>

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
                    <Text style={styles.version}>App CXP v2.0</Text>
                </View>
            </KeyboardAvoidingView>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    safeArea: {
        flex: 1,
        backgroundColor: Colors.light.background,
    },
    keyboardView: {
        flex: 1,
    },
    container: {
        flex: 1,
        justifyContent: 'center',
        paddingHorizontal: 20,
        width: Platform.OS === 'web' ? Math.min(width, 400) : '100%',
        alignSelf: 'center',
    },
    logoContainer: {
        alignItems: 'center',
        marginBottom: 20,
    },
    logo: {
        width: 540,
        height: 180,
    },
    title: {
        fontSize: 32,
        fontWeight: 'bold',
        color: Colors.light.primary,
        textAlign: 'center',
        marginBottom: 5,
    },
    subtitle: {
        fontSize: 18,
        color: Colors.light.textMuted,
        textAlign: 'center',
        marginBottom: 30,
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
        ...Platform.select({
            ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 3 },
            android: { elevation: 2 },
            web: { boxShadow: '0px 2px 3px rgba(0,0,0,0.1)' } as any,
        }),
    },
    button: {
        backgroundColor: Colors.light.primary,
        padding: 15,
        borderRadius: 8,
        alignItems: 'center',
        marginTop: 10,
        ...Platform.select({
            ios: { shadowColor: Colors.light.primary, shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.3, shadowRadius: 5 },
            android: { elevation: 4 },
            web: { boxShadow: `0px 4px 5px ${Colors.light.primary}4D` } as any,
        }),
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
