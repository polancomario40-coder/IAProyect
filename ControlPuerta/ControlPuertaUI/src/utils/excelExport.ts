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
      'Fecha': '2026-11-03',
      'No. conduce': '672764',
      'Producto': 'GRAVA DE 3/4',
      'Mina': 'Mina Haina',
      'Planta': 'Metaldom',
      'Cantidad': 27.43,
      'Precio': 850.00,
      'Total': 23315.50
    },
    {
      'Fecha': '2026-11-03',
      'No. conduce': '362953',
      'Producto': 'ARENA GRIS',
      'Mina': 'Mina San Cristobal',
      'Planta': 'Metaldom',
      'Cantidad': 25.70,
      'Precio': 700.00,
      'Total': 17990.00
    }
  ];

  const ws = XLSX.utils.json_to_sheet(data);

  ws['!cols'] = [
    { wch: 15 }, // Fecha
    { wch: 18 }, // No. conduce
    { wch: 25 }, // Producto
    { wch: 22 }, // Mina
    { wch: 20 }, // Planta
    { wch: 15 }, // Cantidad
    { wch: 15 }, // Precio
    { wch: 16 }  // Total
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'PLANTILLA');

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
