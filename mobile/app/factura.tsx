import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, ScrollView, TouchableOpacity, StyleSheet, Alert, ActivityIndicator, Platform } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../services/api';
import { Colors } from '../constants/Colors';

export default function NuevaFacturaScreen() {
    const params = useLocalSearchParams();
    const idSuplidor = Number(params.idSuplidor);
    const nombre = params.nombre as string;
    const rnc = params.rnc as string;
    const diasCredito = Number(params.diasCredito) || 0;
    const pedirNCF = params.pedirNCF === '1';

    const router = useRouter();

    // Seccion 1: Info General
    const [fechaEmision, setFechaEmision] = useState(new Date().toISOString().split('T')[0]);
    const [fechaVencimiento, setFechaVencimiento] = useState('');
    const [ncf, setNcf] = useState('');
    const [referencia, setReferencia] = useState('');

    // Seccion 2: Montos
    const [subtotal, setSubtotal] = useState('0');
    const [itbis, setItbis] = useState('0');
    const [total, setTotal] = useState('0');

    // Seccion 3: Detalle
    const [concepto, setConcepto] = useState('');

    const [loading, setLoading] = useState(false);

    // Auto-calcular Fecha de Vencimiento
    useEffect(() => {
        if (fechaEmision) {
            const emision = new Date(fechaEmision);
            if (!isNaN(emision.getTime())) {
                emision.setDate(emision.getDate() + diasCredito);
                setFechaVencimiento(emision.toISOString().split('T')[0]);
            }
        }
    }, [fechaEmision, diasCredito]);

    // Auto-calcular Total
    useEffect(() => {
        const valSub = parseFloat(subtotal) || 0;
        const valItbis = parseFloat(itbis) || 0;
        setTotal((valSub + valItbis).toFixed(2));
    }, [subtotal, itbis]);

    const handleGuardar = async () => {
        if (!referencia) {
            Alert.alert('Error', 'Debe ingresar el número de factura (Referencia).');
            return;
        }
        if (pedirNCF && !ncf) {
            Alert.alert('NCF Requerido', 'Este suplidor exige número de comprobante fiscal (NCF).');
            return;
        }
        if (parseFloat(total) <= 0) {
            Alert.alert('Error', 'El monto total debe ser mayor a cero.');
            return;
        }

        if (Platform.OS === 'web') {
            const confirmed = window.confirm('¿Desea registrar esta factura?');
            if (confirmed) {
                submitFactura();
            }
        } else {
            Alert.alert(
                'Confirmación',
                '¿Desea registrar esta factura?',
                [
                    { text: 'Cancelar', style: 'cancel' },
                    {
                        text: 'Sí, Registrar',
                        style: 'default',
                        onPress: submitFactura
                    }
                ]
            );
        }
    };

    const submitFactura = async () => {
        setLoading(true);
        try {
            const response = await api.post('/cxpdocumento', {
                idSuplidor,
                fechaEmision: new Date(fechaEmision).toISOString(),
                vencimiento: new Date(fechaVencimiento).toISOString(),
                referencia,
                compFiscal: ncf,
                concepto,
                valor: parseFloat(subtotal) || 0,
                montoImpuestos: parseFloat(itbis) || 0,
                total: parseFloat(total) || 0,
                rnc,
                nombre
            });

            router.replace({
                pathname: '/confirmacion',
                params: { idDocumento: response.data.idDocumento }
            });
        } catch (error: any) {
            console.error("CATCH ERROR:", error);

            let msg = 'No se pudo guardar la factura';
            if (error.response) {
                // The request was made and the server responded with a status code outside of the range of 2xx
                console.error("Response data:", error.response.data);
                msg = error.response.data?.mensaje || error.response.data || msg;
            } else if (error.request) {
                // The request was made but no response was received
                msg = 'Error de red. No se pudo conectar al servidor.';
            } else {
                // Something happened in setting up the request
                msg = error.message;
            }

            Alert.alert('Error', typeof msg === 'string' ? msg : JSON.stringify(msg));
        } finally {
            setLoading(false);
        }
    };

    return (
        <ScrollView style={styles.container} contentContainerStyle={styles.content}>

            {/* SECCION 1 */}
            <View style={styles.section}>
                <Text style={styles.sectionTitle}>Sección 1: Información General</Text>

                <Text style={styles.label}>Suplidor</Text>
                <TextInput style={[styles.input, styles.inputReadonly]} value={nombre} editable={false} />

                <Text style={styles.label}>Fecha Emisión (YYYY-MM-DD)</Text>
                <TextInput style={styles.input} value={fechaEmision} onChangeText={setFechaEmision} />

                <Text style={styles.label}>Fecha Vencimiento (Autocalculado: {diasCredito} días)</Text>
                <TextInput style={[styles.input, styles.inputReadonly]} value={fechaVencimiento} editable={false} />

                <Text style={styles.label}>Número Factura (Referencia) *</Text>
                <TextInput style={styles.input} value={referencia} onChangeText={setReferencia} />

                <Text style={[styles.label, pedirNCF && !ncf ? { color: Colors.light.danger } : null]}>
                    NCF {pedirNCF ? '*' : '(Opcional)'}
                </Text>
                <TextInput
                    style={[styles.input, pedirNCF && !ncf ? { borderColor: Colors.light.danger, borderWidth: 1 } : null]}
                    value={ncf}
                    onChangeText={setNcf}
                />
            </View>

            {/* SECCION 2 */}
            <View style={styles.section}>
                <Text style={styles.sectionTitle}>Sección 2: Montos</Text>

                <Text style={styles.label}>Subtotal</Text>
                <TextInput style={styles.input} value={subtotal} onChangeText={setSubtotal} keyboardType="numeric" />

                <Text style={styles.label}>ITBIS</Text>
                <TextInput style={styles.input} value={itbis} onChangeText={setItbis} keyboardType="numeric" />

                <Text style={styles.label}>Total (Auto)</Text>
                <TextInput style={[styles.input, styles.inputTotal]} value={total} editable={false} />
            </View>

            {/* SECCION 3 */}
            <View style={styles.section}>
                <Text style={styles.sectionTitle}>Sección 3: Detalle</Text>
                <Text style={styles.label}>Concepto</Text>
                <TextInput
                    style={[styles.input, { height: 80, textAlignVertical: 'top' }]}
                    value={concepto}
                    onChangeText={setConcepto}
                    multiline
                />
            </View>

            <TouchableOpacity
                style={[styles.button, loading && { opacity: 0.7 }]}
                onPress={handleGuardar}
                disabled={loading}
            >
                {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.buttonText}>Guardar Factura</Text>}
            </TouchableOpacity>

        </ScrollView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: Colors.light.background,
    },
    content: {
        padding: 20,
        paddingBottom: 40,
    },
    section: {
        backgroundColor: Colors.light.card,
        padding: 15,
        borderRadius: 8,
        marginBottom: 20,
        borderWidth: 1,
        borderColor: Colors.light.border,
    },
    sectionTitle: {
        fontSize: 16,
        fontWeight: 'bold',
        color: Colors.light.primary,
        marginBottom: 15,
        borderBottomWidth: 1,
        borderBottomColor: Colors.light.border,
        paddingBottom: 5,
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
    inputTotal: {
        backgroundColor: '#DEF7EC',
        color: '#03543F',
        fontWeight: 'bold',
        fontSize: 18,
    },
    button: {
        backgroundColor: Colors.light.primary,
        padding: 18,
        borderRadius: 8,
        alignItems: 'center',
        marginVertical: 10,
    },
    buttonText: {
        color: '#FFF',
        fontSize: 18,
        fontWeight: 'bold',
    }
});
