import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, ScrollView, TouchableOpacity, StyleSheet, Alert, ActivityIndicator, Platform, Image } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import * as ImageManipulator from 'expo-image-manipulator';
import { Picker } from '@react-native-picker/picker';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../services/api';
import storageService from '../services/storage';
import { Colors } from '../constants/Colors';

interface ClaseGasto {
    idClasegasto: string;
    claseGasto: string;
}

interface Moneda {
    idMoneda: number;
    nombre: string;
}

interface FormaPago {
    idPagoForma: number;
    nombre: string;
}

const DEFAULT_MONEDA_ID = 1;
const DEFAULT_PAGO_ID = 4;

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
    const [esServicio, setEsServicio] = useState<boolean>(false);

    // Seccion 2: Montos
    const [subtotal, setSubtotal] = useState('');
    const [itbis, setItbis] = useState('');
    const [total, setTotal] = useState('');

    // Extra: ClaseGasto, Moneda, y Forma Pago
    const [clases, setClases] = useState<ClaseGasto[]>([]);
    const [idClasegasto, setIdClasegasto] = useState('');

    const [monedas, setMonedas] = useState<Moneda[]>([]);
    const [idMoneda, setIdMoneda] = useState<number>(DEFAULT_MONEDA_ID);

    const [formasPago, setFormasPago] = useState<FormaPago[]>([]);
    const [idPagoForma, setIdPagoForma] = useState<number>(DEFAULT_PAGO_ID);

    // Seccion 3: Detalle
    const [concepto, setConcepto] = useState('');
    const [fotoFactura, setFotoFactura] = useState<string | null>(null);

    const [loading, setLoading] = useState(false);
    const [isScanning, setIsScanning] = useState(false);

    // Cargar Catálogos DGII, Monedas y Formas de Pago
    useEffect(() => {
        const fetchCatalogs = async () => {
            try {
                // Fetch DGII
                const resClase = await api.get('/clasegasto');
                setClases(resClase.data);

                const lastClase = await storageService.getItem('@last_clasegasto');
                if (lastClase) {
                    setIdClasegasto(lastClase);
                } else if (resClase.data.length > 0) {
                    setIdClasegasto(resClase.data[0].idClasegasto);
                }

                // Fetch Monedas
                const resMonedas = await api.get('/monedas');
                setMonedas(resMonedas.data);

                // Fetch Formas Pago
                const resFormas = await api.get('/formaspago');
                setFormasPago(resFormas.data);

                // Rehidratar Sticky Settings desde Storage
                const lastMoneda = await storageService.getItem('@last_moneda');
                if (lastMoneda) {
                    setIdMoneda(Number(lastMoneda));
                }

                const lastPago = await storageService.getItem('@last_pagoforma');
                if (lastPago) {
                    setIdPagoForma(Number(lastPago));
                }

            } catch (error) {
                console.error('Error fetching catalogs', error);
            }
        };
        fetchCatalogs();
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

    // Sticky Settings Handlers
    const handleClasegastoChange = async (val: string) => {
        setIdClasegasto(val);
        await storageService.setItem('@last_clasegasto', val);
    };

    const handleMonedaChange = async (val: number) => {
        setIdMoneda(val);
        await storageService.setItem('@last_moneda', val.toString());
    };

    const handlePagoFormaChange = async (val: number) => {
        setIdPagoForma(val);
        await storageService.setItem('@last_pagoforma', val.toString());
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

    const procesarImagen = async (uri: string) => {
        try {
            const manipResult = await ImageManipulator.manipulateAsync(
                uri,
                [{ resize: { width: 1024 } }],
                { compress: 0.5, format: ImageManipulator.SaveFormat.JPEG, base64: true }
            );
            if (manipResult.base64) {
                setFotoFactura(manipResult.base64);
                await procesarOCR(manipResult.base64);
            }
        } catch (error) {
            displayAlert('Error', 'No se pudo procesar la imagen.');
            console.error(error);
        }
    };

    const procesarOCR = async (base64: string) => {
        setIsScanning(true);
        try {
            const resp = await api.post('/cxpdocumento/escanear', { fotoBase64: base64 });
            const data = resp.data;
            if (data && data.success) {
                if (data.rnc || data.RNC) setReferencia(data.rnc || data.RNC);
                if (data.ncf || data.NCF) setNcf(data.ncf || data.NCF);
                if (data.fecha || data.Fecha) setFechaEmision((data.fecha || data.Fecha).split('T')[0]);
                if (data.totalBienes || data.TotalBienes) handleSubtotalChange((data.totalBienes || data.TotalBienes).toString());

                displayAlert('OCR Exitoso', 'Los datos de la factura han sido extraídos y autocompletados.');
            }
        } catch (error) {
            console.error('OCR Error:', error);
            displayAlert('Error OCR', 'Falló la extracción automática de datos. Por favor digite manual.');
        } finally {
            setIsScanning(false);
        }
    };

    const handleTomarFoto = async () => {
        const { status } = await ImagePicker.requestCameraPermissionsAsync();
        if (status !== 'granted') {
            displayAlert('Permiso Denegado', 'Se necesita acceso a la cámara para tomar fotos.');
            return;
        }

        const result = await ImagePicker.launchCameraAsync({
            mediaTypes: ['images'],
            allowsEditing: false,
            quality: 1, // Will compress later down the pipeline with manipulator
        });

        if (!result.canceled && result.assets && result.assets.length > 0) {
            await procesarImagen(result.assets[0].uri);
        }
    };

    const handleSeleccionarGaleria = async () => {
        const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (status !== 'granted') {
            displayAlert('Permiso Denegado', 'Se necesita acceso a la galería.');
            return;
        }

        const result = await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ['images'],
            allowsEditing: false,
            quality: 1,
        });

        if (!result.canceled && result.assets && result.assets.length > 0) {
            await procesarImagen(result.assets[0].uri);
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
                esServicio,
                valor: parseFloat(subtotal) || 0,
                montoImpuestos: parseFloat(itbis) || 0,
                total: parseFloat(total) || 0,
                idClasegasto,
                idMoneda,
                idPagoForma,
                rnc,
                nombre,
                fotoBase64: fotoFactura
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

                <Text style={styles.label}>Tipo de Factura</Text>
                <View style={styles.toggleContainer}>
                    <TouchableOpacity
                        style={[styles.toggleButton, !esServicio && styles.toggleButtonActive]}
                        onPress={() => setEsServicio(false)}
                    >
                        <Text style={[styles.toggleText, !esServicio && styles.toggleTextActive]}>📦 Bienes</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                        style={[styles.toggleButton, esServicio && styles.toggleButtonActive]}
                        onPress={() => setEsServicio(true)}
                    >
                        <Text style={[styles.toggleText, esServicio && styles.toggleTextActive]}>🛠️ Servicios</Text>
                    </TouchableOpacity>
                </View>

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
                        onValueChange={(itemValue: string) => handleClasegastoChange(itemValue)}
                    >
                        {clases.map(c => (
                            <Picker.Item key={c.idClasegasto} label={c.claseGasto} value={c.idClasegasto} />
                        ))}
                    </Picker>
                </View>

                <Text style={styles.label}>Moneda</Text>
                <View style={styles.pickerContainer}>
                    <Picker selectedValue={idMoneda} onValueChange={(val) => handleMonedaChange(Number(val))}>
                        {monedas.map(m => <Picker.Item key={m.idMoneda} label={m.nombre} value={m.idMoneda} />)}
                    </Picker>
                </View>

                <Text style={styles.label}>Forma de Pago</Text>
                <View style={styles.pickerContainer}>
                    <Picker selectedValue={idPagoForma} onValueChange={(val) => handlePagoFormaChange(Number(val))}>
                        {formasPago.map(f => <Picker.Item key={f.idPagoForma} label={f.nombre} value={f.idPagoForma} />)}
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

                <Text style={[styles.sectionTitle, { marginTop: 15 }]}>Adjuntos</Text>
                {!fotoFactura ? (
                    <View style={styles.attachmentButtons}>
                        <TouchableOpacity style={styles.buttonSecondary} onPress={handleTomarFoto}>
                            <Text style={styles.buttonTextSecondary}>📸 Escanear Factura</Text>
                        </TouchableOpacity>
                        <TouchableOpacity style={[styles.buttonSecondary, { marginTop: 10 }]} onPress={handleSeleccionarGaleria}>
                            <Text style={styles.buttonTextSecondary}>🖼️ Seleccionar de Galería</Text>
                        </TouchableOpacity>
                    </View>
                ) : (
                    <View style={styles.thumbnailContainer}>
                        <Image
                            source={{ uri: `data:image/jpeg;base64,${fotoFactura}` }}
                            style={styles.thumbnail}
                        />
                        {isScanning ? (
                            <View style={{ marginVertical: 10, alignItems: 'center' }}>
                                <ActivityIndicator size="large" color={Colors.light.primary} />
                                <Text style={{ color: Colors.light.primary, marginTop: 10, fontWeight: 'bold' }}>Analizando recibo con IA...</Text>
                            </View>
                        ) : (
                            <View style={styles.thumbnailActions}>
                                <TouchableOpacity style={[styles.buttonSecondary, { flex: 1, marginRight: 5 }]} onPress={handleTomarFoto}>
                                    <Text style={styles.buttonTextSecondary}>🔄 Retomar</Text>
                                </TouchableOpacity>
                                <TouchableOpacity style={[styles.buttonDanger, { flex: 1, marginLeft: 5 }]} onPress={() => setFotoFactura(null)}>
                                    <Text style={styles.buttonTextSecondary}>🗑️ Eliminar</Text>
                                </TouchableOpacity>
                            </View>
                        )}
                    </View>
                )}
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
    },
    toggleContainer: {
        flexDirection: 'row',
        marginBottom: 15,
        borderRadius: 8,
        backgroundColor: Colors.light.card,
        borderWidth: 1,
        borderColor: Colors.light.primary,
        overflow: 'hidden'
    },
    toggleButton: {
        flex: 1,
        paddingVertical: 12,
        alignItems: 'center',
        backgroundColor: Colors.light.card,
    },
    toggleButtonActive: {
        backgroundColor: Colors.light.primary,
    },
    toggleText: {
        fontSize: 14,
        fontWeight: 'bold',
        color: Colors.light.primary,
    },
    toggleTextActive: {
        color: '#FFF',
    },
    attachmentButtons: {
        marginBottom: 5,
    },
    buttonSecondary: {
        backgroundColor: Colors.light.card,
        borderWidth: 1,
        borderColor: Colors.light.primary,
        padding: 15,
        borderRadius: 8,
        alignItems: 'center',
    },
    buttonDanger: {
        backgroundColor: Colors.light.card,
        borderWidth: 1,
        borderColor: Colors.light.danger,
        padding: 15,
        borderRadius: 8,
        alignItems: 'center',
    },
    buttonTextSecondary: {
        color: Colors.light.primary,
        fontSize: 16,
        fontWeight: 'bold',
    },
    thumbnailContainer: {
        alignItems: 'center',
        marginBottom: 5,
    },
    thumbnail: {
        width: 200,
        height: 250,
        borderRadius: 8,
        marginBottom: 10,
        resizeMode: 'contain',
        backgroundColor: '#E5E7EB',
    },
    thumbnailActions: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        width: '100%',
    }
});
