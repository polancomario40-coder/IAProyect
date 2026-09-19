import * as XLSX from 'xlsx';

export const exportarExcelAgregados = (items: any[], fechaDesde: string, fechaHasta: string) => {
  const data = items.map(item => ({
    'Fecha': item.fechaEntrada ? new Date(item.fechaEntrada).toLocaleString() : '-',
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
    'Planta': item.idAlmacen || '-',
    'Status': item.status || '-'
  }));

  const ws = XLSX.utils.json_to_sheet(data);

  ws['!cols'] = [
    { wch: 19 },
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
    { wch: 16 },
    { wch: 16 },
    { wch: 12 },
    { wch: 16 },
    { wch: 14 },
    { wch: 28 },
    { wch: 28 },
    { wch: 28 },
    { wch: 15 },
    { wch: 14 }
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, 'Control_Transporte');

  const nombreArchivo = `Reporte_Transporte_${fechaDesde}_al_${fechaHasta}.xlsx`;
  XLSX.writeFile(wb, nombreArchivo);
};
