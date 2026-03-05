import React, { useContext } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { AuthContext } from '../context/AuthContext';
import { Colors } from '../constants/Colors';

export default function DashboardScreen() {
    const { usuario, empresa, logout } = useContext(AuthContext);
    const router = useRouter();

    const handleLogout = async () => {
        await logout();
        router.replace('/');
    };

    return (
        <View style={styles.container}>
            <View style={styles.header}>
                <Text style={styles.welcome}>Hola, {usuario?.Nombre || 'Usuario'}</Text>
                <Text style={styles.company}>{empresa?.nombre || 'Empresa Local'}</Text>
            </View>

            <View style={styles.menu}>
                <TouchableOpacity
                    style={styles.menuItem}
                    onPress={() => router.push('/suplidores')}
                >
                    <Text style={styles.menuText}>➕ Nueva Factura</Text>
                </TouchableOpacity>

                <TouchableOpacity
                    style={styles.menuItemOutline}
                // onPress={() => router.push('/registradas')} // Para futuro
                >
                    <Text style={styles.menuTextOutline}>📄 Facturas Registradas</Text>
                </TouchableOpacity>
            </View>

            <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
                <Text style={styles.logoutText}>🚪 Cerrar Sesión</Text>
            </TouchableOpacity>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.light.background,
        padding: 20,
        justifyContent: 'space-between',
    },
    header: {
        marginTop: 20,
    },
    welcome: {
        fontSize: 28,
        fontWeight: 'bold',
        color: Colors.light.text,
    },
    company: {
        fontSize: 16,
        color: Colors.light.primary,
        marginTop: 5,
    },
    menu: {
        flex: 1,
        justifyContent: 'center',
    },
    menuItem: {
        backgroundColor: Colors.light.primary,
        padding: 20,
        borderRadius: 8,
        alignItems: 'center',
        marginBottom: 20,
    },
    menuText: {
        color: '#FFF',
        fontSize: 18,
        fontWeight: 'bold',
    },
    menuItemOutline: {
        backgroundColor: Colors.light.card,
        padding: 20,
        borderRadius: 8,
        alignItems: 'center',
        borderWidth: 1,
        borderColor: Colors.light.primary,
    },
    menuTextOutline: {
        color: Colors.light.primary,
        fontSize: 18,
        fontWeight: 'bold',
    },
    logoutButton: {
        padding: 15,
        alignItems: 'center',
        marginBottom: 20,
    },
    logoutText: {
        color: Colors.light.danger,
        fontSize: 16,
        fontWeight: 'bold',
    }
});
