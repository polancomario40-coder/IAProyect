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
  const data = [
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
      'No. conduce': '363021',
      'Producto': 'ARENA GRIS',
      'Mina': 'Cantera Bisonó',
      'Planta': 'Metaldom',
      'Cantidad': 25.21,
      'Precio': 700.00,
      'Total': 17647.00
    }
  ];

  const ws = XLSX.utils.json_to_sheet(data);

  ws['!cols'] = [
    { wch: 15 }, // Fecha
    { wch: 18 }, // No. conduce
    { wch: 26 }, // Producto
    { wch: 24 }, // Mina
    { wch: 20 }, // Planta
    { wch: 16 }, // Cantidad
    { wch: 16 }, // Precio
    { wch: 18 }  // Total
  ];

  const catData = [
    { 'PRODUCTOS AUTORIZADOS': 'ARENA GRIS', 'PLANTAS DESTINO': 'Metaldom', 'MINAS / CANTERAS': 'Cantera San Cristóbal' },
    { 'PRODUCTOS AUTORIZADOS': 'ARENA LAVADA', 'PLANTAS DESTINO': 'Haina', 'MINAS / CANTERAS': 'Cantera Bisonó' },
    { 'PRODUCTOS AUTORIZADOS': 'GRAVA DE 3/4"', 'PLANTAS DESTINO': 'Circunvalacion', 'MINAS / CANTERAS': 'Cantera Haina' },
    { 'PRODUCTOS AUTORIZADOS': 'GRAVILLA DE 3/8"', 'PLANTAS DESTINO': 'Esperanza', 'MINAS / CANTERAS': 'Cantera Baní' },
    { 'PRODUCTOS AUTORIZADOS': 'CEMENTO GRIS PORTLAND', 'PLANTAS DESTINO': 'Barahona', 'MINAS / CANTERAS': 'Cantera Nizao' },
    { 'PRODUCTOS AUTORIZADOS': 'CASCAJO', 'PLANTAS DESTINO': 'Punta Cana', 'MINAS / CANTERAS': 'Cantera Palenque' },
    { 'PRODUCTOS AUTORIZADOS': 'CORALINA', 'PLANTAS DESTINO': 'Agua Clara', 'MINAS / CANTERAS': 'Otra' },
    { 'PRODUCTOS AUTORIZADOS': 'BASE', 'PLANTAS DESTINO': '', 'MINAS / CANTERAS': '' },
    { 'PRODUCTOS AUTORIZADOS': 'SUB-BASE', 'PLANTAS DESTINO': '', 'MINAS / CANTERAS': '' },
    { 'PRODUCTOS AUTORIZADOS': 'CALICHE', 'PLANTAS DESTINO': '', 'MINAS / CANTERAS': '' }
  ];
  const wsCat = XLSX.utils.json_to_sheet(catData);
  wsCat['!cols'] = [{ wch: 28 }, { wch: 22 }, { wch: 26 }];

  const insData = [
    { 'REGLA': '1. Fecha', 'INSTRUCCION': 'Coloque la fecha en formato AAAA-MM-DD (ej: 2026-11-04).' },
    { 'REGLA': '2. No. conduce', 'INSTRUCCION': 'Digite el número exacto del conduce físico sin caracteres adicionales.' },
    { 'REGLA': '3. Producto', 'INSTRUCCION': 'Escriba o elija el producto autorizado según la pestaña CATALOGOS.' },
    { 'REGLA': '4. Mina', 'INSTRUCCION': 'Indique la cantera o mina de procedencia del material.' },
    { 'REGLA': '5. Planta', 'INSTRUCCION': 'Indique la planta donde se entregó la mercancía (ej: Metaldom, Haina).' },
    { 'REGLA': '6. Cantidad', 'INSTRUCCION': 'Digite la cantidad en metros cúbicos o toneladas recibidas.' },
    { 'REGLA': '7. Precio', 'INSTRUCCION': 'Precio unitario pactado sin símbolos de moneda.' },
    { 'REGLA': '8. Total', 'INSTRUCCION': 'Se calcula automáticamente (Cantidad x Precio).' },
    { 'REGLA': '9. Auditoría', 'INSTRUCCION': 'Los conduces serán validados con el sistema de control de entrada para calificar pago.' }
  ];
  const wsIns = XLSX.utils.json_to_sheet(insData);
  wsIns['!cols'] = [{ wch: 18 }, { wch: 80 }];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'PLANTILLA');
  XLSX.utils.book_append_sheet(wb, wsCat, 'CATALOGOS');
  XLSX.utils.book_append_sheet(wb, wsIns, 'INSTRUCCIONES');

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
