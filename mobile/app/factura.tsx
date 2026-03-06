import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, ScrollView, TouchableOpacity, StyleSheet, Alert, ActivityIndicator, Platform } from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../services/api';
import { Colors } from '../constants/Colors';

interface ClaseGasto {
    idClasegasto: string;
    claseGasto: string;
}

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
    const [subtotal, setSubtotal] = useState('');
    const [itbis, setItbis] = useState('');
    const [total, setTotal] = useState('');

    // Extra: ClaseGasto
    const [clases, setClases] = useState<ClaseGasto[]>([]);
    const [idClasegasto, setIdClasegasto] = useState('');

    // Seccion 3: Detalle
    const [concepto, setConcepto] = useState('');

    const [loading, setLoading] = useState(false);

    // Cargar Catálogo DGII
    useEffect(() => {
        const fetchClases = async () => {
            try {
                const response = await api.get('/clasegasto');
                setClases(response.data);
                if (response.data.length > 0) {
                    setIdClasegasto(response.data[0].idClasegasto);
                }
            } catch (error) {
                console.error('Error fetching clase gasto', error);
            }
        };
        fetchClases();
    }, []);

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

    // Auto-calcular Montos Bidireccionales
    // Cambio Subtotal -> Actualiza ITBIS y Total
    const handleSubtotalChange = (val: string) => {
        setSubtotal(val);
        const numVal = parseFloat(val) || 0;
        const newItbis = numVal * 0.18;
        const newTotal = numVal + newItbis;

        setItbis(newItbis.toFixed(2));
        setTotal(newTotal.toFixed(2));
    };

    // Cambio Total -> Extrae Subtotal e ITBIS
    const handleTotalChange = (val: string) => {
        setTotal(val);
        const numTotal = parseFloat(val) || 0;
        const newSubtotal = numTotal / 1.18;
        const newItbis = numTotal - newSubtotal;

        setSubtotal(newSubtotal.toFixed(2));
        setItbis(newItbis.toFixed(2));
    };

    // Cambio Manual de Itbis -> Suma de nuevo el Total (manteniendo subtotal firme)
    const handleItbisChange = (val: string) => {
        setItbis(val);
        const numSub = parseFloat(subtotal) || 0;
        const numItbis = parseFloat(val) || 0;
        setTotal((numSub + numItbis).toFixed(2));
    };

    const validateNCF = (val: string) => {
        // Regex: starts with B or E, then digits. Total 11 or 13 chars
        const regex = /^[BE]\d{10,12}$/i;
        return regex.test(val);
    };

    const displayAlert = (title: string, msg: string) => {
        if (Platform.OS === 'web') {
            window.alert(`${title}: ${msg}`);
        } else {
            Alert.alert(title, msg);
        }
    };

    const handleGuardar = async () => {
        if (!referencia || referencia.trim() === '') {
            displayAlert('Error', 'Debe ingresar el número de factura (Referencia).');
            return;
        }
        if (pedirNCF) {
            if (!ncf || ncf.trim() === '') {
                displayAlert('NCF Requerido', 'Este suplidor exige número de comprobante fiscal (NCF).');
                return;
            }
            if (!validateNCF(ncf)) {
                displayAlert('NCF Inválido', 'El NCF debe empezar con B o E y tener 11 o 13 caracteres en total.');
                return;
            }
        }

        const numTotal = parseFloat(total);
        if (isNaN(numTotal) || numTotal <= 0) {
            displayAlert('Error', 'El monto total debe ser un número mayor a cero.');
            return;
        }

        if (Platform.OS === 'web') {
            submitFactura();
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
                idClasegasto,
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

            const finalMsg = typeof msg === 'string' ? msg : JSON.stringify(msg);
            displayAlert('Error', finalMsg);
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
                <Text style={styles.sectionTitle}>Sección 2: Clasificación y Montos</Text>

                <Text style={styles.label}>Clase de Gasto (DGII)</Text>
                <View style={styles.pickerContainer}>
                    <Picker
                        selectedValue={idClasegasto}
                        onValueChange={(itemValue: string) => setIdClasegasto(itemValue)}
                    >
                        {clases.map(c => (
                            <Picker.Item key={c.idClasegasto} label={c.claseGasto} value={c.idClasegasto} />
                        ))}
                    </Picker>
                </View>

                <Text style={styles.label}>Total Factura (Extrae Subtotal/ITBIS al digitar)</Text>
                <TextInput style={[styles.input, styles.inputTotal]} value={total} onChangeText={handleTotalChange} keyboardType="numeric" placeholder="0.00" />

                <Text style={styles.label}>Subtotal (Altera ITBIS/Total al digitar)</Text>
                <TextInput style={styles.input} value={subtotal} onChangeText={handleSubtotalChange} keyboardType="numeric" placeholder="0.00" />

                <Text style={styles.label}>ITBIS (Altera Total al digitar)</Text>
                <TextInput style={styles.input} value={itbis} onChangeText={handleItbisChange} keyboardType="numeric" placeholder="0.00" />
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
    },
    pickerContainer: {
        backgroundColor: Colors.light.background,
        borderWidth: 1,
        borderColor: Colors.light.border,
        borderRadius: 6,
        marginBottom: 15,
        overflow: 'hidden'
    }
});
