import * as XLSX from 'xlsx';

export const exportarExcelAgregados = (items: any[], fechaDesde: string, fechaHasta: string) => {
  const data = items.map(item => ({
    'Fecha': item.fechaEntrada ? new Date(item.fechaEntrada).toLocaleString() : '-',
    'Planta': item.almacen || item.idAlmacen || '-',
    'Entrada Almacén': item.proMov || '-',
    'Recepción': item.numRecepcionOC || item.conduceTransporte || '-',
    'OC': item.ordenNumero ? `#${item.ordenNumero}` : 'Sin OC',
    'No. Conduce': item.conduce || '-',
    'Conduce Transporte': item.conduceTransporte || '-',
    'Suplidor': item.suplidor || '-',
    'Producto': item.producto ? (item.idProducto ? `[${item.idProducto}] ${item.producto}` : item.producto) : '-',
    'Cantidad Recibida': Number(item.cantidadRecibida || item.cantidadDeclarada || 0),
    'Unidad': item.idUnidad || 'Mts3',
    'Cant. Almacén': Number(item.cantidadAlmacen || item.cantidadRecibida || item.cantidadDeclarada || 0),
    'Unidad Almacén': item.idUnidadAlmacen || item.idUnidad || 'Mts3',
    'Status': item.status || '-'
  }));

  const ws = XLSX.utils.json_to_sheet(data);

  ws['!cols'] = [
    { wch: 19 },
    { wch: 20 },
    { wch: 16 },
    { wch: 16 },
    { wch: 12 },
    { wch: 16 },
    { wch: 20 },
    { wch: 32 },
    { wch: 35 },
    { wch: 16 },
    { wch: 12 },
    { wch: 16 },
    { wch: 14 },
    { wch: 14 }
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Recepcion_Agregados');

  const nombreArchivo = `Reporte_Recepcion_Agregados_${fechaDesde}_al_${fechaHasta}.xlsx`;
  XLSX.writeFile(wb, nombreArchivo);
};

export const exportarExcelTransporte = (items: any[], fechaDesde: string, fechaHasta: string) => {
  const data = items.map(item => ({
    'Fecha': item.fechaEntrada ? new Date(item.fechaEntrada).toLocaleString() : '-',
    'Planta': item.almacen || item.idAlmacen || '-',
    'Entrada Almacén': item.proMov || '-',
    'Recepción': item.numRecepcionOC || item.conduceTransporte || '-',
    'OC': item.ordenNumero ? `#${item.ordenNumero}` : 'Sin OC',
    'No. Conduce': item.conduce || '-',
    'Placa': item.placa || '-',
    'Transportista': item.transportista || '-',
    'Chofer': item.nombreChofer || '-',
    'Producto': item.producto || '-',
    'Cantidad': Number(item.cantidadRecibida || item.cantidadDeclarada || 0),
    'Unidad': item.idUnidad || 'Mts3',
    'Status': item.status || '-'
  }));

  const ws = XLSX.utils.json_to_sheet(data);

  ws['!cols'] = [
    { wch: 19 },
    { wch: 20 },
    { wch: 16 },
    { wch: 16 },
    { wch: 12 },
    { wch: 16 },
    { wch: 14 },
    { wch: 28 },
    { wch: 28 },
    { wch: 28 },
    { wch: 15 },
    { wch: 14 },
    { wch: 14 }
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Control_Transporte');

  const nombreArchivo = `Reporte_Transporte_${fechaDesde}_al_${fechaHasta}.xlsx`;
  XLSX.writeFile(wb, nombreArchivo);
};

export const descargarPlantillaSuplidorExcel = () => {
  // Hoja 1: PLANTILLA OFICIAL EN BLANCO (Directa desde Fila 1 para que el suplidor la llene)
  const headers = [
    'Fecha', 
    'No. conduce', 
    'Producto', 
    'Mina', 
    'Planta', 
    'Cantidad', 
    'Precio', 
    'Total'
  ];

  // Matriz vacía con solo la fila de encabezados
  const wsData = [headers];
  const ws = XLSX.utils.aoa_to_sheet(wsData);

  ws['!cols'] = [
    { wch: 15 }, // Fecha
    { wch: 18 }, // No. conduce
    { wch: 28 }, // Producto
    { wch: 24 }, // Mina
    { wch: 20 }, // Planta
    { wch: 16 }, // Cantidad
    { wch: 16 }, // Precio
    { wch: 18 }  // Total
  ];

  // Hoja 2: CATÁLOGOS DE CONSULTA
  const catData = [
    { 'PRODUCTOS AUTORIZADOS': 'GRAVA DE 3/4"', 'PLANTAS DE ENTREGA': 'Metaldom', 'MINAS Y CANTERAS RECURRENTES': 'Cantera San Cristóbal' },
    { 'PRODUCTOS AUTORIZADOS': 'ARENA GRIS', 'PLANTAS DE ENTREGA': 'Haina', 'MINAS Y CANTERAS RECURRENTES': 'Cantera Bisonó' },
    { 'PRODUCTOS AUTORIZADOS': 'ARENA LAVADA', 'PLANTAS DE ENTREGA': 'Circunvalacion', 'MINAS Y CANTERAS RECURRENTES': 'Cantera Haina' },
    { 'PRODUCTOS AUTORIZADOS': 'GRAVILLA DE 3/8"', 'PLANTAS DE ENTREGA': 'Esperanza', 'MINAS Y CANTERAS RECURRENTES': 'Cantera Baní' },
    { 'PRODUCTOS AUTORIZADOS': 'CEMENTO GRIS PORTLAND', 'PLANTAS DE ENTREGA': 'Barahona', 'MINAS Y CANTERAS RECURRENTES': 'Cantera Nizao' },
    { 'PRODUCTOS AUTORIZADOS': 'CASCAJO', 'PLANTAS DE ENTREGA': 'Punta Cana', 'MINAS Y CANTERAS RECURRENTES': 'Cantera Palenque' },
    { 'PRODUCTOS AUTORIZADOS': 'CORALINA', 'PLANTAS DE ENTREGA': 'Agua Clara', 'MINAS Y CANTERAS RECURRENTES': 'Otras Canteras' },
    { 'PRODUCTOS AUTORIZADOS': 'BASE', 'PLANTAS DE ENTREGA': 'SanIsidro', 'MINAS Y CANTERAS RECURRENTES': '' },
    { 'PRODUCTOS AUTORIZADOS': 'SUB-BASE', 'PLANTAS DE ENTREGA': 'UveroAlto', 'MINAS Y CANTERAS RECURRENTES': '' },
    { 'PRODUCTOS AUTORIZADOS': 'CALICHE', 'PLANTAS DE ENTREGA': 'Miches', 'MINAS Y CANTERAS RECURRENTES': '' }
  ];
  const wsCat = XLSX.utils.json_to_sheet(catData);
  wsCat['!cols'] = [{ wch: 30 }, { wch: 24 }, { wch: 30 }];

  // Hoja 3: GUÍA Y REGLAS DE LLENADO
  const insData = [
    { 'REGLA': '1. Estado de Plantilla', 'INSTRUCCIÓN': 'Esta hoja se suministra en blanco para ser completada con sus conduces entregados en planta.' },
    { 'REGLA': '2. Encabezados', 'INSTRUCCIÓN': 'No modifique el nombre ni el orden de las columnas de la hoja "PLANTILLA".' },
    { 'REGLA': '3. Fecha', 'INSTRUCCIÓN': 'Indique la fecha de entrega en formato AAAA-MM-DD (ej: 2026-11-04) o formato de fecha de Excel.' },
    { 'REGLA': '4. No. conduce', 'INSTRUCCIÓN': 'Digite el número exacto del conduce físico entregado al chofer/planta.' },
    { 'REGLA': '5. Producto', 'INSTRUCCIÓN': 'Escriba o elija el producto según la lista de "CATALOGOS" (ej: GRAVA DE 3/4", ARENA GRIS).' },
    { 'REGLA': '6. Mina', 'INSTRUCCIÓN': 'Indique la cantera o mina de origen donde se extrajo el material.' },
    { 'REGLA': '7. Planta', 'INSTRUCCIÓN': 'Indique la planta de destino donde se descargó (ej: Metaldom, Haina, Circunvalacion).' },
    { 'REGLA': '8. Cantidad', 'INSTRUCCIÓN': 'Cantidad en M3 o toneladas recibidas.' },
    { 'REGLA': '9. Precio', 'INSTRUCCIÓN': 'Precio unitario pactado sin signos de pesos ni letras.' },
    { 'REGLA': '10. Total', 'INSTRUCCIÓN': 'Multiplicación de Cantidad x Precio.' },
    { 'REGLA': '11. Validación', 'INSTRUCCIÓN': 'Cada conduce será conciliado de manera automática contra las recepciones de báscula/puerta antes de autorizar el pago.' }
  ];
  const wsIns = XLSX.utils.json_to_sheet(insData);
  wsIns['!cols'] = [{ wch: 24 }, { wch: 90 }];

  // Hoja 4: EJEMPLO ILUSTRATIVO (Para que el suplidor vea cómo debe verse su reporte)
  const ejemploData = [
    {
      'Fecha': '2026-11-04',
      'No. conduce': '672867',
      'Producto': 'GRAVA DE 3/4"',
      'Mina': 'Cantera San Cristóbal',
      'Planta': 'Metaldom',
      'Cantidad': 26.46,
      'Precio': 850.00,
      'Total': 22491.00
    },
    {
      'Fecha': '2026-11-04',
      'No. conduce': '672812',
      'Producto': 'ARENA GRIS',
      'Mina': 'Cantera San Cristóbal',
      'Planta': 'Metaldom',
      'Cantidad': 26.61,
      'Precio': 700.00,
      'Total': 18627.00
    }
  ];
  const wsEjemplo = XLSX.utils.json_to_sheet(ejemploData);
  wsEjemplo['!cols'] = [
    { wch: 15 }, { wch: 18 }, { wch: 28 }, { wch: 24 }, { wch: 20 }, { wch: 16 }, { wch: 16 }, { wch: 18 }
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'PLANTILLA');
  XLSX.utils.book_append_sheet(wb, wsCat, 'CATALOGOS');
  XLSX.utils.book_append_sheet(wb, wsIns, 'INSTRUCCIONES');
  XLSX.utils.book_append_sheet(wb, wsEjemplo, 'EJEMPLO_LLENADO');

  XLSX.writeFile(wb, 'PLANTILLA_CONDUCES_SUPLIDOR.xlsx');
};

export const exportarResultadoConciliacionExcel = (resumen: any, items: any[]) => {
  const data = items.map(item => ({
    'Fecha': item.fechaConduce ? new Date(item.fechaConduce).toLocaleDateString() : '-',
    'No. Conduce': item.noConduce,
    'Producto Declarado': item.producto || '-',
    'Mina': item.mina || '-',
    'Planta Declarada': item.planta || '-',
    'Cant. Declarada': Number(item.cantidadDeclarada || 0),
    'Precio Unitario': Number(item.precioUnitario || 0),
    'Total Reclamado': Number(item.totalReclamado || 0),
    'Estado de Cuadre': item.estadoCuadre === 'CALIFICA_PAGO' 
      ? 'CALIFICA PARA PAGO' 
      : (item.estadoCuadre === 'PENDIENTE_RECEPCION' ? 'PENDIENTE RECEPCIÓN' : 'NO CALIFICA'),
    'Motivo / Diagnóstico': item.motivoRechazo || '-',
    'Estado Pago': item.estadoPago || 'PENDIENTE',
    'Entrada Almacén': item.proMov || '-',
    'Recepción OC': item.numRecepcionOC || '-',
    'OC #': item.ordenNumero ? `#${item.ordenNumero}` : '-',
    'Producto Sistema': item.productoEncontrado || '-',
    'Planta Sistema': item.plantaEncontrada || '-',
    'Cant. Sistema': item.cantidadSistema != null ? Number(item.cantidadSistema) : '-',
    'Unidad': item.unidadSistema || 'Mts3',
    'Total Aprobado': item.totalAprobado != null ? Number(item.totalAprobado) : 0
  }));

  const ws = XLSX.utils.json_to_sheet(data);

  ws['!cols'] = [
    { wch: 13 }, // Fecha
    { wch: 18 }, // No. Conduce
    { wch: 25 }, // Producto Declarado
    { wch: 20 }, // Mina
    { wch: 20 }, // Planta Declarada
    { wch: 16 }, // Cant. Declarada
    { wch: 15 }, // Precio Unitario
    { wch: 16 }, // Total Reclamado
    { wch: 22 }, // Estado de Cuadre
    { wch: 45 }, // Motivo / Diagnóstico
    { wch: 16 }, // Estado Pago
    { wch: 18 }, // Entrada Almacén
    { wch: 18 }, // Recepción OC
    { wch: 12 }, // OC #
    { wch: 25 }, // Producto Sistema
    { wch: 20 }, // Planta Sistema
    { wch: 15 }, // Cant. Sistema
    { wch: 10 }, // Unidad
    { wch: 16 }  // Total Aprobado
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Conciliacion_Conduces');

  const nombre = `Auditoria_Conciliacion_${resumen?.suplidor ? resumen.suplidor.replace(/[^a-zA-Z0-9]/g, '_') : 'Suplidor'}_${new Date().toISOString().split('T')[0]}.xlsx`;
  XLSX.writeFile(wb, nombre);
};
