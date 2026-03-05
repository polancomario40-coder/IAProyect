import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import api from '../services/api';
import { Colors } from '../constants/Colors';

interface Empresa {
    idEmpresa: string;
    empresa: string;
    rnc: string;
}

export default function SelectEmpresaScreen() {
    const [empresas, setEmpresas] = useState<Empresa[]>([]);
    const [loading, setLoading] = useState(true);
    const router = useRouter();

    useEffect(() => {
        const fetchEmpresas = async () => {
            try {
                const response = await api.get('/empresas');
                setEmpresas(response.data);
            } catch (error) {
                console.error('Error fetching empresas', error);
            } finally {
                setLoading(false);
            }
        };
        fetchEmpresas();
    }, []);

    const handleSelect = (empresa: Empresa) => {
        router.push({ pathname: '/login', params: { idEmpresa: empresa.idEmpresa, nombre: empresa.empresa } });
    };

    return (
        <View style={styles.container}>
            <Text style={styles.title}>Seleccionar Empresa</Text>

            {loading ? (
                <ActivityIndicator size="large" color={Colors.light.primary} />
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
                />
            )}
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.light.background,
        paddingTop: 60,
        paddingHorizontal: 20,
    },
    title: {
        fontSize: 24,
        fontWeight: 'bold',
        color: Colors.light.text,
        textAlign: 'center',
        marginBottom: 30,
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
    },
    cardTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: Colors.light.primary,
        marginBottom: 4,
    },
    cardSubtitle: {
        fontSize: 14,
        color: Colors.light.textMuted,
    },
});
