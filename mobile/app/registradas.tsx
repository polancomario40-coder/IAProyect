import React, { useState, useEffect, useCallback } from 'react';
import { 
    View, Text, StyleSheet, FlatList, TouchableOpacity, 
    ActivityIndicator, RefreshControl, Modal, TextInput,
    Image as RNImage, Platform 
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../services/api';
import { Colors } from '../constants/Colors';
import dayjs from 'dayjs';

export default function FacturasRegistradasScreen() {
    const router = useRouter();
    const [facturas, setFacturas] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    
    // Search state
    const [searchQuery, setSearchQuery] = useState('');
    const [debouncedQuery, setDebouncedQuery] = useState('');

    // Modal state
    const [modalVisible, setModalVisible] = useState(false);
    const [selectedFactura, setSelectedFactura] = useState<any>(null);
    const [imagenBase64, setImagenBase64] = useState<string | null>(null);
    const [loadingImage, setLoadingImage] = useState(false);

    // Debounce logic
    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedQuery(searchQuery);
        }, 500);

        return () => {
            clearTimeout(handler);
        };
    }, [searchQuery]);

    const fetchFacturas = async (query: string = '') => {
        setLoading(true);
        try {
            console.log(`Fetching facturas registradas with query: '${query}'...`);
            const response = await api.get(`/cxpdocumento/registradas?buscar=${encodeURIComponent(query)}`);
            console.log(`Received ${response.data.length} facturas`);
            setFacturas(response.data);
        } catch (error) {
            console.error("Error fetching facturas", error);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchFacturas(debouncedQuery);
    }, [debouncedQuery]);

    const onRefresh = useCallback(() => {
        setRefreshing(true);
        fetchFacturas(debouncedQuery);
    }, [debouncedQuery]);

    const openFacturaDetails = async (factura: any) => {
        setSelectedFactura(factura);
        setImagenBase64(null);
        setModalVisible(true);

        if (factura.tieneImagen) {
            setLoadingImage(true);
            try {
                const response = await api.get(`/cxpdocumento/${factura.guidDocumento}/imagen`);
                if (response.data && response.data.success) {
                    setImagenBase64(response.data.imagenBase64);
                }
            } catch (error) {
                console.error("Error fetching invoice image", error);
            } finally {
                setLoadingImage(false);
            }
        }
    };

    const renderItem = ({ item }: { item: any }) => (
        <TouchableOpacity 
            style={styles.card} 
            onPress={() => openFacturaDetails(item)}
            activeOpacity={0.7}
        >
            <View style={styles.cardHeader}>
                <Text style={styles.dateText}>
                    {dayjs(item.fechaEmision).format('DD/MM/YYYY')}
                </Text>
                {item.tieneImagen && (
                    <Ionicons name="image-outline" size={20} color={Colors.light.primary} />
                )}
            </View>
            
            <View style={styles.cardBody}>
                <View style={{ flex: 1, paddingRight: 10 }}>
                    <Text style={styles.supplierText} numberOfLines={1}>{item.nombre || 'Sin Nombre'}</Text>
                    <Text style={styles.ncfText}>NCF: {item.compFiscal || 'N/A'}</Text>
                </View>
                <View style={styles.amountContainer}>
                    <Text style={styles.amountText}>
                        ${item.total?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </Text>
                </View>
            </View>
        </TouchableOpacity>
    );

    return (
        <SafeAreaView style={styles.container}>
            <View style={styles.header}>
                <TouchableOpacity onPress={() => router.back()} style={styles.backButton}>
                    <Ionicons name="arrow-back" size={24} color={Colors.light.text} />
                </TouchableOpacity>
                <Text style={styles.headerTitle}>Facturas Registradas</Text>
                <View style={{ width: 24 }} />
            </View>

            <View style={styles.searchContainer}>
                <Ionicons name="search" size={20} color={Colors.light.textMuted} style={styles.searchIcon} />
                <TextInput
                    style={styles.searchInput}
                    placeholder="Buscar por NCF, Suplidor o Número..."
                    placeholderTextColor={Colors.light.textMuted}
                    value={searchQuery}
                    onChangeText={setSearchQuery}
                />
                {searchQuery.length > 0 && (
                    <TouchableOpacity onPress={() => setSearchQuery('')} style={styles.clearSearchButton}>
                        <Ionicons name="close-circle" size={18} color={Colors.light.textMuted} />
                    </TouchableOpacity>
                )}
            </View>

            {loading ? (
                <View style={styles.centerContainer}>
                    <ActivityIndicator size="large" color={Colors.light.primary} />
                </View>
            ) : (
                <FlatList
                    data={facturas}
                    keyExtractor={(item) => item.idDocumento.toString()}
                    renderItem={renderItem}
                    contentContainerStyle={styles.listContainer}
                    refreshControl={
                        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[Colors.light.primary]} />
                    }
                    ListEmptyComponent={
                        <View style={styles.emptyContainer}>
                            <Ionicons name="document-text-outline" size={60} color={Colors.light.textMuted} />
                            <Text style={styles.emptyText}>No hay facturas registradas</Text>
                        </View>
                    }
                />
            )}

            {/* Modal Detail */}
            <Modal
                animationType="slide"
                transparent={true}
                visible={modalVisible}
                onRequestClose={() => setModalVisible(false)}
            >
                <View style={styles.modalOverlay}>
                    <View style={styles.modalContent}>
                        <View style={styles.modalHeader}>
                            <Text style={styles.modalTitle}>Detalle de Factura</Text>
                            <TouchableOpacity onPress={() => setModalVisible(false)}>
                                <Ionicons name="close-circle" size={28} color={Colors.light.textMuted} />
                            </TouchableOpacity>
                        </View>

                        {selectedFactura && (
                            <View style={styles.modalBody}>
                                <Text style={styles.detailLabel}>Suplidor:</Text>
                                <Text style={styles.detailValue}>{selectedFactura.nombre || 'N/A'}</Text>

                                <Text style={styles.detailLabel}>RNC:</Text>
                                <Text style={styles.detailValue}>{selectedFactura.rnc || 'N/A'}</Text>

                                <Text style={styles.detailLabel}>NCF:</Text>
                                <Text style={styles.detailValue}>{selectedFactura.compFiscal || 'N/A'}</Text>

                                <Text style={styles.detailLabel}>Fecha de Emisión:</Text>
                                <Text style={styles.detailValue}>{dayjs(selectedFactura.fechaEmision).format('DD/MM/YYYY')}</Text>

                                <Text style={styles.detailLabel}>Concepto:</Text>
                                <Text style={styles.detailValue}>{selectedFactura.concepto || 'Sin concepto'}</Text>

                                <Text style={styles.detailLabel}>Total:</Text>
                                <Text style={styles.detailTotal}>
                                    ${selectedFactura.total?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </Text>

                                {selectedFactura.tieneImagen && (
                                    <View style={styles.imageSection}>
                                        <Text style={styles.detailLabel}>Documento Adjunto:</Text>
                                        {loadingImage ? (
                                            <ActivityIndicator size="small" color={Colors.light.primary} style={{ marginTop: 10 }} />
                                        ) : imagenBase64 ? (
                                            <RNImage 
                                                source={{ uri: `data:image/jpeg;base64,${imagenBase64}` }} 
                                                style={styles.attachedImage} 
                                                resizeMode="contain"
                                            />
                                        ) : (
                                            <Text style={styles.errorText}>No se pudo cargar la imagen.</Text>
                                        )}
                                    </View>
                                )}
                            </View>
                        )}
                    </View>
                </View>
            </Modal>
        </SafeAreaView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.light.background,
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 15,
        paddingVertical: 15,
        borderBottomWidth: 1,
        borderBottomColor: Colors.light.border,
        backgroundColor: Colors.light.card,
    },
    backButton: {
        padding: 5,
    },
    headerTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        color: Colors.light.text,
    },
    searchContainer: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: Colors.light.card,
        marginHorizontal: 15,
        marginTop: 15,
        borderRadius: 10,
        paddingHorizontal: 12,
        height: 45,
        borderWidth: 1,
        borderColor: Colors.light.border,
        ...Platform.select({
            ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 2 },
            android: { elevation: 1 },
            web: { boxShadow: '0px 1px 2px rgba(0,0,0,0.05)' } as any,
        }),
    },
    searchIcon: {
        marginRight: 8,
    },
    searchInput: {
        flex: 1,
        fontSize: 14,
        color: Colors.light.text,
        height: '100%',
    },
    clearSearchButton: {
        padding: 5,
    },
    centerContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    listContainer: {
        padding: 15,
        paddingBottom: 40,
    },
    card: {
        backgroundColor: Colors.light.card,
        borderRadius: 12,
        padding: 15,
        marginBottom: 15,
        borderWidth: 1,
        borderColor: Colors.light.border,
        ...Platform.select({
            ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 4 },
            android: { elevation: 2 },
            web: { boxShadow: '0px 2px 4px rgba(0,0,0,0.05)' } as any,
        }),
    },
    cardHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 10,
    },
    dateText: {
        fontSize: 12,
        color: Colors.light.textMuted,
        fontWeight: '600',
    },
    cardBody: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'flex-end',
    },
    supplierText: {
        fontSize: 16,
        fontWeight: 'bold',
        color: Colors.light.text,
        marginBottom: 4,
    },
    ncfText: {
        fontSize: 13,
        color: Colors.light.textMuted,
    },
    amountContainer: {
        backgroundColor: '#FFF7ED', // Light orange tint
        paddingHorizontal: 8,
        paddingVertical: 4,
        borderRadius: 6,
    },
    amountText: {
        fontSize: 16,
        fontWeight: '700',
        color: Colors.light.primary,
    },
    emptyContainer: {
        marginTop: 50,
        alignItems: 'center',
    },
    emptyText: {
        marginTop: 10,
        fontSize: 16,
        color: Colors.light.textMuted,
    },
    modalOverlay: {
        flex: 1,
        backgroundColor: 'rgba(0,0,0,0.5)',
        justifyContent: 'flex-end',
    },
    modalContent: {
        backgroundColor: Colors.light.card,
        borderTopLeftRadius: 20,
        borderTopRightRadius: 20,
        padding: 20,
        maxHeight: '90%',
    },
    modalHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 20,
        borderBottomWidth: 1,
        borderBottomColor: Colors.light.border,
        paddingBottom: 10,
    },
    modalTitle: {
        fontSize: 20,
        fontWeight: 'bold',
        color: Colors.light.text,
    },
    modalBody: {
        paddingBottom: 20,
    },
    detailLabel: {
        fontSize: 12,
        color: Colors.light.textMuted,
        marginTop: 12,
        marginBottom: 2,
    },
    detailValue: {
        fontSize: 16,
        color: Colors.light.text,
        fontWeight: '500',
    },
    detailTotal: {
        fontSize: 22,
        color: Colors.light.primary,
        fontWeight: 'bold',
        marginTop: 2,
    },
    imageSection: {
        marginTop: 20,
        borderTopWidth: 1,
        borderTopColor: Colors.light.border,
        paddingTop: 10,
    },
    attachedImage: {
        width: '100%',
        height: 250,
        marginTop: 10,
        borderRadius: 8,
        backgroundColor: '#F3F4F6',
    },
    errorText: {
        color: Colors.light.danger,
        marginTop: 10,
        fontStyle: 'italic',
    }
});
