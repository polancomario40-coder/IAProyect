import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator, Modal, KeyboardAvoidingView, Platform, Alert } from 'react-native';
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

    // Estado Modal
    const [modalVisible, setModalVisible] = useState(false);
    const [nuevoNombre, setNuevoNombre] = useState('');
    const [creandoRapido, setCreandoRapido] = useState(false);

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

    const handleCrearRapido = async () => {
        if (!nuevoNombre.trim()) {
            Alert.alert('Error', 'El nombre comercial es obligatorio.');
            return;
        }

        setCreandoRapido(true);
        try {
            const res = await api.post('/suplidores/rapido', {
                nombre: nuevoNombre,
                rnc: buscar
            });

            setModalVisible(false);
            setNuevoNombre('');

            // Auto-seleccionar y navegar
            handleSelect({
                idSuplidor: res.data.idSuplidor,
                nombre: res.data.nombre,
                rnc: res.data.rnc,
                diasCredito: res.data.diasCredito,
                pedirNCF: res.data.pedirNCF
            });

        } catch (error: any) {
            console.error('Error creando proveedor', error);
            Alert.alert('Error', error.response?.data?.mensaje || 'No se pudo crear el proveedor');
        } finally {
            setCreandoRapido(false);
        }
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
                    ListEmptyComponent={
                        <View style={styles.emptyContainer}>
                            <Text style={styles.emptyText}>Suplidor no encontrado.</Text>
                            <TouchableOpacity style={styles.createButton} onPress={() => setModalVisible(true)}>
                                <Text style={styles.createButtonText}>+ Crear Nuevo Suplidor</Text>
                            </TouchableOpacity>
                        </View>
                    }
                />
            )}

            {/* Modal Creación Rápida */}
            <Modal
                animationType="slide"
                transparent={true}
                visible={modalVisible}
                onRequestClose={() => setModalVisible(false)}
            >
                <KeyboardAvoidingView
                    behavior={Platform.OS === 'ios' ? 'padding' : undefined}
                    style={styles.modalOverlay}
                >
                    <View style={styles.modalView}>
                        <Text style={styles.modalTitle}>Crear Suplidor (Rápido)</Text>

                        <Text style={styles.label}>RNC / Cédula</Text>
                        <TextInput
                            style={[styles.input, styles.inputReadonly]}
                            value={buscar}
                            editable={false}
                        />

                        <Text style={styles.label}>Nombre Comercial *</Text>
                        <TextInput
                            style={styles.input}
                            value={nuevoNombre}
                            onChangeText={setNuevoNombre}
                            placeholder="Ej. Distribuidora XYZ"
                            autoFocus
                        />

                        <View style={styles.modalActions}>
                            <TouchableOpacity
                                style={[styles.modalButton, styles.modalButtonCancel]}
                                onPress={() => setModalVisible(false)}
                                disabled={creandoRapido}
                            >
                                <Text style={styles.modalButtonTextCancel}>Cancelar</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                                style={[styles.modalButton, styles.modalButtonPrimary]}
                                onPress={handleCrearRapido}
                                disabled={creandoRapido}
                            >
                                {creandoRapido ? <ActivityIndicator color="#FFF" /> : <Text style={styles.modalButtonTextPrimary}>Guardar y Continuar</Text>}
                            </TouchableOpacity>
                        </View>
                    </View>
                </KeyboardAvoidingView>
            </Modal>
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
    },
    emptyContainer: {
        padding: 40,
        alignItems: 'center',
    },
    emptyText: {
        fontSize: 16,
        color: Colors.light.textMuted,
        marginBottom: 15,
    },
    createButton: {
        backgroundColor: Colors.light.card,
        borderWidth: 1,
        borderColor: Colors.light.primary,
        paddingHorizontal: 20,
        paddingVertical: 12,
        borderRadius: 8,
    },
    createButtonText: {
        color: Colors.light.primary,
        fontWeight: 'bold',
        fontSize: 16,
    },
    modalOverlay: {
        flex: 1,
        backgroundColor: 'rgba(0,0,0,0.5)',
        justifyContent: 'center',
        padding: 20,
    },
    modalView: {
        backgroundColor: Colors.light.background,
        borderRadius: 12,
        padding: 24,
        ...Platform.select({
            ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.25, shadowRadius: 4 },
            android: { elevation: 5 },
            web: { boxShadow: '0px 2px 4px rgba(0,0,0,0.25)' } as any,
        }),
    },
    modalTitle: {
        fontSize: 20,
        fontWeight: 'bold',
        color: Colors.light.primary,
        marginBottom: 20,
        textAlign: 'center',
    },
    label: {
        fontSize: 14,
        color: Colors.light.text,
        marginBottom: 5,
        fontWeight: '600',
    },
    input: {
        backgroundColor: Colors.light.background,
        borderWidth: 1,
        borderColor: Colors.light.border,
        borderRadius: 6,
        padding: 12,
        fontSize: 16,
        marginBottom: 15,
        color: Colors.light.text,
    },
    inputReadonly: {
        backgroundColor: '#E5E7EB',
        color: Colors.light.textMuted,
    },
    modalActions: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        marginTop: 10,
    },
    modalButton: {
        flex: 1,
        padding: 14,
        borderRadius: 8,
        alignItems: 'center',
    },
    modalButtonCancel: {
        backgroundColor: Colors.light.background,
        marginRight: 10,
    },
    modalButtonPrimary: {
        backgroundColor: Colors.light.primary,
    },
    modalButtonTextCancel: {
        color: Colors.light.textMuted,
        fontSize: 16,
        fontWeight: 'bold',
    },
    modalButtonTextPrimary: {
        color: '#FFF',
        fontSize: 16,
        fontWeight: 'bold',
    }
});
