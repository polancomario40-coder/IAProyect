import React, { useEffect, useState, useContext } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import api from '../services/api';
import { AuthContext } from '../context/AuthContext';
import { Colors } from '../constants/Colors';

interface Empresa {
    idEmpresa: string;
    empresa: string;
    rnc: string;
}

export default function SelectEmpresaScreen() {
    const [empresas, setEmpresas] = useState<Empresa[]>([]);
    const [loading, setLoading] = useState(true);
    const { selectEmpresa } = useContext(AuthContext);

    useEffect(() => {
        const fetchEmpresas = async () => {
            try {
                const response = await api.get('/usuario/empresas');
                setEmpresas(response.data);
            } catch (error) {
                console.error('Error fetching empresas', error);
            } finally {
                setLoading(false);
            }
        };
        fetchEmpresas();
    }, []);

    const handleSelect = async (empresa: Empresa) => {
        await selectEmpresa(empresa);
    };

    return (
        <SafeAreaView style={styles.safeArea}>
            <View style={styles.container}>
                <Text style={styles.title}>Dataflow CXP</Text>
                <Text style={styles.subtitle}>Selecciona tu Empresa</Text>

                {loading ? (
                    <ActivityIndicator size="large" color="#1F3A8A" style={{ marginTop: 50 }} />
                ) : (
                    <FlatList
                        data={empresas}
                        keyExtractor={(item) => item.idEmpresa}
                        renderItem={({ item }) => (
                            <TouchableOpacity style={styles.card} onPress={() => handleSelect(item)}>
                                <Text style={styles.cardTitle}>{item.empresa}</Text>
                                <Text style={styles.cardSubtitle}>RNC: {item.rnc}</Text>
                            </TouchableOpacity>
                        )}
                        contentContainerStyle={styles.list}
                        ListEmptyComponent={<Text style={styles.emptyText}>No tienes empresas asignadas.</Text>}
                    />
                )}
            </View>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    safeArea: {
        flex: 1,
        backgroundColor: Colors.light.background,
    },
    container: {
        flex: 1,
        paddingTop: 40,
        paddingHorizontal: 20,
    },
    title: {
        fontSize: 28,
        fontWeight: 'bold',
        color: '#1F3A8A',
        textAlign: 'center',
        marginBottom: 5,
    },
    subtitle: {
        fontSize: 16,
        color: Colors.light.textMuted,
        textAlign: 'center',
        marginBottom: 30,
        fontWeight: '600',
    },
    list: {
        paddingBottom: 20,
    },
    card: {
        backgroundColor: Colors.light.card,
        padding: 20,
        borderRadius: 8,
        marginBottom: 15,
        borderWidth: 1,
        borderColor: Colors.light.border,
        ...Platform.select({
            ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 3 },
            android: { elevation: 2 },
            web: { boxShadow: '0px 2px 3px rgba(0,0,0,0.1)' } as any,
        }),
    },
    cardTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: '#1F3A8A',
        marginBottom: 4,
    },
    cardSubtitle: {
        fontSize: 14,
        color: Colors.light.textMuted,
    },
    emptyText: {
        textAlign: 'center',
        color: Colors.light.textMuted,
        marginTop: 50,
        fontSize: 16,
    }
});
