import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import api from '../services/api';
import { Colors } from '../constants/Colors';

interface Suplidor {
    idSuplidor: number;
    nombre: string;
    rnc: string;
    diasCredito: number;
    pedirNCF: boolean;
}

export default function SuplidoresScreen() {
    const [suplidores, setSuplidores] = useState<Suplidor[]>([]);
    const [filtered, setFiltered] = useState<Suplidor[]>([]);
    const [buscar, setBuscar] = useState('');
    const [loading, setLoading] = useState(true);
    const router = useRouter();

    useEffect(() => {
        const fetchSuplidores = async () => {
            try {
                const response = await api.get('/suplidores');
                setSuplidores(response.data);
                setFiltered(response.data);
            } catch (error) {
                console.error('Error fetching suplidores', error);
            } finally {
                setLoading(false);
            }
        };
        fetchSuplidores();
    }, []);

    const handleSearch = (text: string) => {
        setBuscar(text);
        if (!text) {
            setFiltered(suplidores);
        } else {
            const lower = text.toLowerCase();
            setFiltered(suplidores.filter(s =>
                s.nombre.toLowerCase().includes(lower) ||
                s.rnc?.includes(lower)
            ));
        }
    };

    const handleSelect = (s: Suplidor) => {
        router.push({
            pathname: '/factura',
            params: {
                idSuplidor: s.idSuplidor,
                nombre: s.nombre,
                rnc: s.rnc,
                diasCredito: s.diasCredito,
                pedirNCF: s.pedirNCF ? '1' : '0'
            }
        });
    };

    return (
        <View style={styles.container}>
            <TextInput
                style={styles.searchInput}
                placeholder="🔍 Buscar por Nombre o RNC..."
                placeholderTextColor={Colors.light.textMuted}
                value={buscar}
                onChangeText={handleSearch}
            />

            {loading ? (
                <ActivityIndicator size="large" color={Colors.light.primary} style={{ marginTop: 20 }} />
            ) : (
                <FlatList
                    data={filtered}
                    keyExtractor={(item) => item.idSuplidor.toString()}
                    renderItem={({ item }) => (
                        <TouchableOpacity style={styles.row} onPress={() => handleSelect(item)}>
                            <Text style={styles.rowTitle}>{item.nombre}</Text>
                            <Text style={styles.rowSubtitle}>{item.rnc || 'Sin RNC'}</Text>
                        </TouchableOpacity>
                    )}
                />
            )}
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.light.background,
    },
    searchInput: {
        backgroundColor: Colors.light.card,
        padding: 15,
        fontSize: 16,
        borderBottomWidth: 1,
        borderColor: Colors.light.border,
        color: Colors.light.text,
    },
    row: {
        padding: 20,
        borderBottomWidth: StyleSheet.hairlineWidth,
        borderColor: Colors.light.border,
        backgroundColor: Colors.light.card,
    },
    rowTitle: {
        fontSize: 16,
        fontWeight: 'bold',
        color: Colors.light.text,
        marginBottom: 4,
    },
    rowSubtitle: {
        fontSize: 14,
        color: Colors.light.textMuted,
    }
});
