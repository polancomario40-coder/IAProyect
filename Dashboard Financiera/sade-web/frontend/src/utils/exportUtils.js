import * as XLSX from 'xlsx'
import { jsPDF } from 'jspdf'
import autoTable from 'jspdf-autotable'

const fmtMoney = (n) => {
  const val = Number(n) || 0
  return 'RD$\u00A0' + val.toLocaleString('es-DO', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

const fmtDate = (d) =>
  d
    ? new Date(d).toLocaleDateString('es-DO', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      })
    : '—'

/**
 * Construye una hoja de Excel con membrete institucional y título dinámico en las primeras filas
 */
function crearHojaConTitulo(rows, tituloPrincipal, subtitulo = '') {
  const fechaEmision = `${new Date().toLocaleDateString('es-DO')} ${new Date().toLocaleTimeString('es-DO')}`
  const ws = XLSX.utils.aoa_to_sheet([
    ['SADE WEB — SISTEMA DE GESTIÓN FINANCIERA'],
    [(tituloPrincipal || 'INFORME FINANCIERO').toUpperCase()],
    [subtitulo ? `${subtitulo}  |  Emisión: ${fechaEmision}` : `Fecha de Emisión: ${fechaEmision}`],
    [],
  ])
  XLSX.utils.sheet_add_json(ws, rows, { origin: 'A5' })
  return ws
}

/**
 * Exporta el listado de clientes a Excel (.xlsx) con título dinámico según filtros
 */
export function exportarClientesExcel(
  clientes,
  nombreArchivo = 'Cartera_Clientes_SADE',
  titulo = 'INFORME DE CARTERA DE CLIENTES'
) {
  if (!clientes || clientes.length === 0) return

  const rows = clientes.map((c) => ({
    'ID Cliente': c.idCliente,
    'Nombre Completo': c.nombreCompleto || '—',
    'Cédula': c.cedula || '—',
    'Teléfono': c.telefono || '—',
    'Oficina': c.oficina || '—',
    'Empresa': c.empresa || '—',
    'Cargo': c.cargoEmpresa || '—',
    'Salario': c.salario ? Number(c.salario) : 0,
    'Préstamo #': c.numeroPrestamo || '—',
    'Monto Original': c.montoActual ? Number(c.montoActual) : 0,
    'Capital Pagado': c.capitalPagado ? Number(c.capitalPagado) : 0,
    'Balance Total': c.balanceActual ? Number(c.balanceActual) : 0,
    'Balance Capital': c.balanceCapital ? Number(c.balanceCapital) : 0,
    'Monto Saldar Hoy': c.montoSaldarHoy ? Number(c.montoSaldarHoy) : 0,
    'Clasificación': c.clasificacion || '—',
    'Condición': c.estadoCartera || '—',
    'Creador': c.creador || '—',
    'Fecha Registro': fmtDate(c.fechaRegistro),
    'Ref 1 Nombre': c.nombreRef1 || '—',
    'Ref 1 Teléfono': c.telRef1 || '—',
    'Ref 2 Nombre': c.nombreRef2 || '—',
    'Ref 2 Teléfono': c.telRef2 || '—',
  }))

  const worksheet = crearHojaConTitulo(
    rows,
    titulo,
    `Total de Clientes Exportados: ${clientes.length}`
  )
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Cartera Clientes')
  XLSX.writeFile(workbook, `${nombreArchivo}_${new Date().toISOString().slice(0, 10)}.xlsx`)
}

/**
 * Exporta el listado de clientes a PDF con diseño corporativo y título dinámico
 */
export function exportarClientesPDF(
  clientes,
  titulo = 'Informe de Cartera de Clientes',
  nombreArchivo = 'Cartera_Clientes'
) {
  if (!clientes || clientes.length === 0) return

  const doc = new jsPDF('landscape', 'pt', 'letter')

  // Encabezado
  doc.setFontSize(15)
  doc.setTextColor(30, 58, 95) // Color primario SADE #1e3a5f
  doc.text('SADE WEB — SISTEMA DE GESTIÓN FINANCIERA', 40, 38)

  doc.setFontSize(11)
  doc.setTextColor(30)
  doc.text(titulo.toUpperCase(), 40, 56)

  doc.setFontSize(9.5)
  doc.setTextColor(100)
  doc.text(`Fecha de emisión: ${new Date().toLocaleDateString('es-DO')} ${new Date().toLocaleTimeString('es-DO')}  |  Total de registros: ${clientes.length}`, 40, 72)

  const tableColumn = [
    'Cliente',
    'Cédula',
    'Empresa',
    'Préstamo #',
    'Balance Total',
    'Saldar Hoy',
    'Clasificación',
    'Creador',
    'Fecha',
  ]

  const tableRows = clientes.map((c) => [
    c.nombreCompleto || '—',
    c.cedula || '—',
    (c.empresa || '—').slice(0, 25),
    c.numeroPrestamo ? `#${c.numeroPrestamo}` : '—',
    fmtMoney(c.balanceActual),
    fmtMoney(c.montoSaldarHoy),
    c.clasificacion || '—',
    c.creador || '—',
    fmtDate(c.fechaRegistro),
  ])

  autoTable(doc, {
    head: [tableColumn],
    body: tableRows,
    startY: 86,
    theme: 'grid',
    styles: {
      fontSize: 8,
      cellPadding: 4,
    },
    headStyles: {
      fillColor: [30, 58, 95],
      textColor: [255, 255, 255],
      fontStyle: 'bold',
    },
    alternateRowStyles: {
      fillColor: [248, 250, 252],
    },
  })

  doc.save(`${nombreArchivo}_${new Date().toISOString().slice(0, 10)}.pdf`)
}

/**
 * Exporta el historial integral de un cliente a Excel
 */
export function exportarHistorialClienteExcel(cliente, prestamos) {
  if (!cliente) return

  const infoCliente = [
    { 'Campo': 'ID Cliente', 'Valor': cliente.idCliente },
    { 'Campo': 'Nombre Completo', 'Valor': cliente.nombreCompleto },
    { 'Campo': 'Cédula', 'Valor': cliente.cedula },
    { 'Campo': 'Teléfono', 'Valor': cliente.telefono },
    { 'Campo': 'Oficina', 'Valor': cliente.oficina },
    { 'Campo': 'Empresa', 'Valor': cliente.empresa },
    { 'Campo': 'Cargo', 'Valor': cliente.cargoEmpresa },
    { 'Campo': 'Salario', 'Valor': cliente.salario ? Number(cliente.salario) : 0 },
    { 'Campo': 'Creador', 'Valor': cliente.creador },
    { 'Campo': 'Clasificación', 'Valor': cliente.clasificacionGlobal },
    { 'Campo': 'Total Préstamos Tomados', 'Valor': cliente.totalPrestamos },
    { 'Campo': 'Préstamos Activos', 'Valor': cliente.prestamosActivos },
    { 'Campo': 'Referencia 1', 'Valor': `${cliente.nombreRef1 || ''} (${cliente.telRef1 || ''})` },
    { 'Campo': 'Referencia 2', 'Valor': `${cliente.nombreRef2 || ''} (${cliente.telRef2 || ''})` },
  ]

  const prestamosRows = (prestamos || []).map((p) => ({
    'Préstamo #': p.numeroPrestamo,
    'Fecha Otorgado': fmtDate(p.fechaPrestamo),
    'Monto Original': Number(p.montoOriginal),
    'Interés Original': Number(p.interesOriginal),
    'Total Original': Number(p.totalOriginal),
    'Tasa (%)': Number(p.tasa),
    'Capital Pagado': Number(p.capitalPagado),
    'Total Pagado': Number(p.totalPagado),
    'Balance Capital': Number(p.balanceCapital),
    'Balance Total': Number(p.balanceTotal),
    'Monto Saldar Hoy': Number(p.montoSaldarHoy),
    'Estado': p.estado,
    'Creador': p.creador,
  }))

  const workbook = XLSX.utils.book_new()
  const wsInfo = crearHojaConTitulo(
    infoCliente,
    `ESTADO DE CUENTA INTEGRAL — CLIENTE: ${cliente.nombreCompleto || ''}`,
    `Empresa / Cartera: ${cliente.empresa || '—'} | Cédula: ${cliente.cedula || '—'}`
  )
  const wsPrestamos = crearHojaConTitulo(
    prestamosRows,
    `HISTORIAL DE PRÉSTAMOS — CLIENTE: ${cliente.nombreCompleto || ''}`,
    `Empresa / Cartera: ${cliente.empresa || '—'} | Total Préstamos: ${cliente.totalPrestamos || 0}`
  )

  XLSX.utils.book_append_sheet(workbook, wsInfo, 'Datos Cliente')
  XLSX.utils.book_append_sheet(workbook, wsPrestamos, 'Historial Préstamos')

  XLSX.writeFile(workbook, `Historial_${cliente.cedula || cliente.idCliente}_${new Date().toISOString().slice(0, 10)}.xlsx`)
}

/**
 * Exporta el historial integral de un cliente a PDF
 */
export function exportarHistorialClientePDF(cliente, prestamos) {
  if (!cliente) return

  const doc = new jsPDF('portrait', 'pt', 'letter')

  // Header
  doc.setFontSize(16)
  doc.setTextColor(30, 58, 95)
  doc.text('SADE WEB — ESTADO DE CUENTA INTEGRAL', 40, 40)

  doc.setFontSize(11)
  doc.setTextColor(70)
  doc.text(`Cliente: ${cliente.nombreCompleto} (ID #${cliente.idCliente})`, 40, 60)
  doc.text(`Cédula: ${cliente.cedula || '—'}  |  Teléfono: ${cliente.telefono || '—'}`, 40, 75)
  doc.text(`Empresa: ${cliente.empresa || '—'}  |  Oficina: ${cliente.oficina || '—'}`, 40, 90)
  doc.text(`Perfil: ${cliente.clasificacionGlobal} (${cliente.totalPrestamos} préstamos en historial, ${cliente.prestamosActivos} activo(s))`, 40, 105)
  doc.text(`Creador/Operador: ${cliente.creador || '—'}`, 40, 120)

  // Referencias
  doc.setFontSize(9)
  doc.setTextColor(100)
  doc.text(`Ref 1: ${cliente.nombreRef1 || '—'} (${cliente.telRef1 || '—'}) - ${cliente.dirRef1 || '—'}`, 40, 138)
  doc.text(`Ref 2: ${cliente.nombreRef2 || '—'} (${cliente.telRef2 || '—'}) - ${cliente.dirRef2 || '—'}`, 40, 150)

  const tableColumn = [
    'Préstamo #',
    'Fecha',
    'Monto',
    'Tasa',
    'Total Pagado',
    'Balance Total',
    'Saldar Hoy',
    'Estado',
  ]

  const tableRows = (prestamos || []).map((p) => [
    `#${p.numeroPrestamo}`,
    fmtDate(p.fechaPrestamo),
    fmtMoney(p.montoOriginal),
    `${p.tasa}%`,
    fmtMoney(p.totalPagado),
    fmtMoney(p.balanceTotal),
    fmtMoney(p.montoSaldarHoy),
    p.estado,
  ])

  autoTable(doc, {
    head: [tableColumn],
    body: tableRows,
    startY: 165,
    theme: 'grid',
    styles: {
      fontSize: 8.5,
      cellPadding: 4,
    },
    headStyles: {
      fillColor: [30, 58, 95],
      textColor: [255, 255, 255],
      fontStyle: 'bold',
    },
    alternateRowStyles: {
      fillColor: [248, 250, 252],
    },
  })

  doc.save(`EstadoCuenta_${cliente.cedula || cliente.idCliente}_${new Date().toISOString().slice(0, 10)}.pdf`)
}

// ═════════════════════════════════════════════════════════════════════════════
// NUEVOS REPORTES ANALÍTICOS (PLANTILLAS OFICIALES EXCEL Y PDF CON TOTALES)
// ═════════════════════════════════════════════════════════════════════════════

/**
 * 1. Exporta el Informe Detalle de Clientes a Excel según la Plantilla (Imagen 1)
 *    Incluye título dinámico (ej. clientes del Bravo) y columna Capital Actual Adeudado
 */
export function exportarReporteDetalleExcel(
  filas = [],
  totales = {},
  nombreArchivo = 'Detalle_Clientes_Quincena',
  titulo = 'INFORME DETALLE DE CLIENTES'
) {
  if (!filas || filas.length === 0) return

  const rows = filas.map((r) => ({
    'CLASIFICACION': r.clasificacion || '',
    'NOMBRE': r.nombreCliente || '',
    'EMPRESA': r.empresa || '',
    'MONTO_PRESTAMO': Number(r.montoPrestamo) || 0,
    'CAPITAL PAGADO': Number(r.capitalPagado) || 0,
    'BALANCE ANTES DEL COBRO': Number(r.balanceAntesCobro) || 0,
    'CAPITAL COBRADO QUINCENA': Number(r.capitalCobradoQuincena) || 0,
    'INTERES COBRADO QUINCENA': Number(r.interesCobradoQuincena) || 0,
    'CAPITAL ACTUAL ADEUDADO': (r.capitalActualAdeudado && Number(r.capitalActualAdeudado) !== 0)
      ? Number(r.capitalActualAdeudado)
      : Math.max(0, (Number(r.montoPrestamo) || 0) - (Number(r.capitalPagado) || 0)),
    'TASA': Number(r.tasa) || 0,
    'COMENTARIO': r.comentario || '',
  }))

  // Fila de Totales en pesos ($) al final
  rows.push({
    'CLASIFICACION': 'TOTAL GENERAL',
    'NOMBRE': `Total Registros: ${totales.totalRegistros ?? filas.length}`,
    'EMPRESA': '',
    'MONTO_PRESTAMO': Number(totales.totalMontoPrestamo) || 0,
    'CAPITAL PAGADO': Number(totales.totalCapitalPagado) || 0,
    'BALANCE ANTES DEL COBRO': Number(totales.totalBalanceAntesCobro) || 0,
    'CAPITAL COBRADO QUINCENA': Number(totales.totalCapitalCobradoQuincena) || 0,
    'INTERES COBRADO QUINCENA': Number(totales.totalInteresCobradoQuincena) || 0,
    'CAPITAL ACTUAL ADEUDADO': (totales.totalCapitalActualAdeudado && Number(totales.totalCapitalActualAdeudado) !== 0)
      ? Number(totales.totalCapitalActualAdeudado)
      : Math.max(0, (Number(totales.totalMontoPrestamo) || 0) - (Number(totales.totalCapitalPagado) || 0)),
    'TASA': Number(totales.tasaPromedio) || 0,
    'COMENTARIO': `Quincena: ${fmtDate(totales.quincenaDesde)} al ${fmtDate(totales.quincenaHasta)}`,
  })

  const subtitulo = `Período / Quincena: ${fmtDate(totales.quincenaDesde)} al ${fmtDate(totales.quincenaHasta)}  |  Total Clientes: ${totales.totalRegistros ?? filas.length}`
  const worksheet = crearHojaConTitulo(rows, titulo, subtitulo)
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Detalle Quincena')
  XLSX.writeFile(workbook, `${nombreArchivo}_${new Date().toISOString().slice(0, 10)}.xlsx`)
}

/**
 * 2. Exporta el Informe Detalle de Clientes a PDF (Diseño formal horizontal con Totales)
 */
export function exportarReporteDetallePDF(
  filas = [],
  totales = {},
  titulo = 'INFORME DETALLE INDIVIDUAL DE CLIENTES',
  nombreArchivo = 'Detalle_Clientes'
) {
  if (!filas || filas.length === 0) return

  const doc = new jsPDF('landscape', 'pt', 'letter')

  // Membrete corporativo
  doc.setFontSize(14)
  doc.setTextColor(30, 58, 95)
  doc.text('SADE WEB — SISTEMA DE GESTIÓN FINANCIERA', 40, 35)

  doc.setFontSize(11)
  doc.setTextColor(30)
  doc.text(titulo.toUpperCase(), 40, 52)

  doc.setFontSize(9)
  doc.setTextColor(100)
  const qStr = totales.quincenaDesde ? ` | Quincena evaluada: ${fmtDate(totales.quincenaDesde)} al ${fmtDate(totales.quincenaHasta)}` : ''
  doc.text(`Fecha de Emisión: ${new Date().toLocaleDateString('es-DO')} ${new Date().toLocaleTimeString('es-DO')}${qStr}`, 40, 67)
  doc.text(`Total de Clientes Listados: ${filas.length}`, 40, 80)

  const tableColumn = [
    'CLASIFICACIÓN',
    'NOMBRE DEL CLIENTE',
    'EMPRESA',
    'MONTO PRÉSTAMO',
    'CAPITAL PAGADO',
    'BAL. ANTES COBRO',
    'CAPITAL COBRADO',
    'INTERÉS COBRADO',
    'CAP. ACTUAL ADEUDADO',
    'TASA',
    'COMENTARIO',
  ]

  const tableRows = filas.map((r) => [
    r.clasificacion || '',
    r.nombreCliente || '',
    r.empresa || '',
    fmtMoney(r.montoPrestamo),
    fmtMoney(r.capitalPagado),
    fmtMoney(r.balanceAntesCobro),
    fmtMoney(r.capitalCobradoQuincena),
    fmtMoney(r.interesCobradoQuincena),
    fmtMoney(
      (r.capitalActualAdeudado && Number(r.capitalActualAdeudado) !== 0)
        ? r.capitalActualAdeudado
        : Math.max(0, (Number(r.montoPrestamo) || 0) - (Number(r.capitalPagado) || 0))
    ),
    `${r.tasa}%`,
    r.comentario || '',
  ])

  // Fila de Totales en negrita al pie
  const footRow = [
    'TOTAL GENERAL',
    `${totales.totalRegistros ?? filas.length} clientes`,
    '',
    fmtMoney(totales.totalMontoPrestamo),
    fmtMoney(totales.totalCapitalPagado),
    fmtMoney(totales.totalBalanceAntesCobro),
    fmtMoney(totales.totalCapitalCobradoQuincena),
    fmtMoney(totales.totalInteresCobradoQuincena),
    fmtMoney(
      (totales.totalCapitalActualAdeudado && Number(totales.totalCapitalActualAdeudado) !== 0)
        ? totales.totalCapitalActualAdeudado
        : Math.max(0, (Number(totales.totalMontoPrestamo) || 0) - (Number(totales.totalCapitalPagado) || 0))
    ),
    `${totales.tasaPromedio ?? 0}%`,
    '',
  ]

  autoTable(doc, {
    head: [tableColumn],
    body: tableRows,
    foot: [footRow],
    startY: 95,
    margin: { left: 25, right: 25 },
    theme: 'grid',
    columnStyles: {
      0: { cellWidth: 50, halign: 'center' },  // CLASIFICACIÓN
      1: { cellWidth: 84, halign: 'left' },    // NOMBRE DEL CLIENTE
      2: { cellWidth: 78, halign: 'left' },    // EMPRESA
      3: { cellWidth: 67, halign: 'right' },   // MONTO PRÉSTAMO
      4: { cellWidth: 65, halign: 'right' },   // CAPITAL PAGADO
      5: { cellWidth: 65, halign: 'right' },   // BAL. ANTES COBRO
      6: { cellWidth: 65, halign: 'right' },   // CAPITAL COBRADO
      7: { cellWidth: 65, halign: 'right' },   // INTERÉS COBRADO
      8: { cellWidth: 67, halign: 'right' },   // CAP. ACTUAL ADEUDADO
      9: { cellWidth: 26, halign: 'center' },  // TASA
      10: { cellWidth: 110, halign: 'left' },  // COMENTARIO
    },
    styles: {
      fontSize: 6.8,
      cellPadding: 2,
      valign: 'middle',
    },
    headStyles: {
      fillColor: [245, 158, 11], // Tono dorado/amarillo como la plantilla del cliente
      textColor: [30, 41, 59],
      fontStyle: 'bold',
      fontSize: 6.8,
      cellPadding: 2.5,
      halign: 'center',
    },
    footStyles: {
      fillColor: [30, 58, 95],
      textColor: [255, 255, 255],
      fontStyle: 'bold',
      fontSize: 6.8,
      cellPadding: 2,
      valign: 'middle',
    },
    alternateRowStyles: {
      fillColor: [248, 250, 252],
    },
  })

  doc.save(`${nombreArchivo}_${new Date().toISOString().slice(0, 10)}.pdf`)
}

/**
 * 3. Exporta el Informe Consolidado por Cartera a Excel según la Plantilla (Imagen 2)
 */
export function exportarReporteCarteraExcel(
  filas = [],
  totales = {},
  nombreArchivo = 'Consolidado_Cartera',
  titulo = 'INFORME GENERAL CONSOLIDADO POR CARTERA'
) {
  if (!filas || filas.length === 0) return

  const rows = filas.map((r) => ({
    'CARTERA': r.cartera || '',
    'BALANCE DE CAPITAL COLOCADO': Number(r.balanceCapitalColocado) || 0,
    'CAPITAL CLIENTES INACTIVOS/CANCELADOS': Number(r.capitalClientesInactivosCancelados) || 0,
    'CAPITAL ACTIVO': Number(r.capitalActivo) || 0,
    'CLIENTES ACTIVOS': Number(r.clientesActivos) || 0,
    'CLIENTES INACTIVOS': Number(r.clientesInactivos) || 0,
    'CAPITAL COBRADO DE LA QUINCENA': Number(r.capitalCobradoQuincena) || 0,
    'INTERES COBRADO DE LA QUINCENA': Number(r.interesCobradoQuincena) || 0,
    'TASA': `${Number(r.tasa) || 0}%`,
  }))

  // Fila de Totales Generales al final
  rows.push({
    'CARTERA': 'TOTAL GENERAL',
    'BALANCE DE CAPITAL COLOCADO': Number(totales.totalBalanceCapitalColocado) || 0,
    'CAPITAL CLIENTES INACTIVOS/CANCELADOS': Number(totales.totalCapitalInactivosCancelados) || 0,
    'CAPITAL ACTIVO': Number(totales.totalCapitalActivo) || 0,
    'CLIENTES ACTIVOS': Number(totales.totalClientesActivos) || 0,
    'CLIENTES INACTIVOS': Number(totales.totalClientesInactivos) || 0,
    'CAPITAL COBRADO DE LA QUINCENA': Number(totales.totalCapitalCobradoQuincena) || 0,
    'INTERES COBRADO DE LA QUINCENA': Number(totales.totalInteresCobradoQuincena) || 0,
    'TASA': `${Number(totales.tasaPromedioPonderada) || 0}%`,
  })

  const subtitulo = `Período / Quincena: ${fmtDate(totales.quincenaDesde)} al ${fmtDate(totales.quincenaHasta)}  |  Total Carteras: ${filas.length}`
  const worksheet = crearHojaConTitulo(rows, titulo, subtitulo)
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Consolidado Cartera')
  XLSX.writeFile(workbook, `${nombreArchivo}_${new Date().toISOString().slice(0, 10)}.xlsx`)
}

/**
 * 4. Exporta el Informe Consolidado por Cartera a PDF
 */
export function exportarReporteCarteraPDF(
  filas = [],
  totales = {},
  titulo = 'INFORME GENERAL CONSOLIDADO POR CARTERA',
  nombreArchivo = 'Consolidado_Cartera'
) {
  if (!filas || filas.length === 0) return

  const doc = new jsPDF('landscape', 'pt', 'letter')

  doc.setFontSize(14)
  doc.setTextColor(30, 58, 95)
  doc.text('SADE WEB — SISTEMA DE GESTIÓN FINANCIERA', 40, 35)

  doc.setFontSize(11)
  doc.setTextColor(30)
  doc.text(titulo.toUpperCase(), 40, 52)

  doc.setFontSize(9)
  doc.setTextColor(100)
  const qStr = totales.quincenaDesde ? ` | Quincena: ${fmtDate(totales.quincenaDesde)} al ${fmtDate(totales.quincenaHasta)}` : ''
  doc.text(`Fecha de Corte: ${fmtDate(totales.fechaCorte || new Date())}${qStr}`, 40, 67)
  doc.text(`Total de Carteras / Empresas: ${filas.length}`, 40, 80)

  const tableColumn = [
    'CARTERA',
    'BAL. CAPITAL COLOCADO',
    'CAP. INACT./CANCELADOS',
    'CAPITAL ACTIVO',
    'CLI. ACT.',
    'CLI. INACT.',
    'CAP. COBRADO QUINCENA',
    'INT. COBRADO QUINCENA',
    'TASA',
  ]

  const tableRows = filas.map((r) => [
    r.cartera || '',
    fmtMoney(r.balanceCapitalColocado),
    fmtMoney(r.capitalClientesInactivosCancelados),
    fmtMoney(r.capitalActivo),
    String(r.clientesActivos ?? 0),
    String(r.clientesInactivos ?? 0),
    fmtMoney(r.capitalCobradoQuincena),
    fmtMoney(r.interesCobradoQuincena),
    `${r.tasa}%`,
  ])

  const footRow = [
    'TOTAL GENERAL',
    fmtMoney(totales.totalBalanceCapitalColocado),
    fmtMoney(totales.totalCapitalInactivosCancelados),
    fmtMoney(totales.totalCapitalActivo),
    String(totales.totalClientesActivos ?? 0),
    String(totales.totalClientesInactivos ?? 0),
    fmtMoney(totales.totalCapitalCobradoQuincena),
    fmtMoney(totales.totalInteresCobradoQuincena),
    `${totales.tasaPromedioPonderada ?? 0}%`,
  ]

  autoTable(doc, {
    head: [tableColumn],
    body: tableRows,
    foot: [footRow],
    startY: 95,
    margin: { left: 25, right: 25 },
    theme: 'grid',
    columnStyles: {
      0: { cellWidth: 162, halign: 'left' },   // CARTERA
      1: { cellWidth: 80, halign: 'right' },   // BAL. CAPITAL COLOCADO
      2: { cellWidth: 80, halign: 'right' },   // CAP. INACT./CANCELADOS
      3: { cellWidth: 80, halign: 'right' },   // CAPITAL ACTIVO
      4: { cellWidth: 42, halign: 'center' },  // CLI. ACT.
      5: { cellWidth: 42, halign: 'center' },  // CLI. INACT.
      6: { cellWidth: 80, halign: 'right' },   // CAP. COBRADO QUINCENA
      7: { cellWidth: 80, halign: 'right' },   // INT. COBRADO QUINCENA
      8: { cellWidth: 36, halign: 'center' },  // TASA
    },
    styles: {
      fontSize: 7.2,
      cellPadding: 2.5,
      valign: 'middle',
    },
    headStyles: {
      fillColor: [245, 158, 11], // Encabezado amarillo como Imagen 2
      textColor: [30, 41, 59],
      fontStyle: 'bold',
      fontSize: 7.2,
      cellPadding: 3,
      halign: 'center',
    },
    footStyles: {
      fillColor: [30, 58, 95],
      textColor: [255, 255, 255],
      fontStyle: 'bold',
      fontSize: 7.2,
      cellPadding: 2.5,
      valign: 'middle',
    },
    alternateRowStyles: {
      fillColor: [248, 250, 252],
    },
  })

  doc.save(`${nombreArchivo}_${new Date().toISOString().slice(0, 10)}.pdf`)
}

/**
 * 5. Exporta el Libro Completo en Excel con Pestañas Múltiples (Como en Imagen 1)
 */
export function exportarReporteCompletoLibroExcel({
  carteras = [],
  totalesCartera = {},
  detalleTodos = [],
  totalesDetalleTodos = {},
  nuevos = [],
  totalesNuevos = {},
  reenganches = [],
  totalesReenganches = {},
  cancelados = [],
  totalesCancelados = {},
  carteraMora = [],
  totalesMora = {},
  nombreArchivo = 'Informe_Financiero_SADE_Completo',
  empresa = '',
  fechaDesde = '',
  fechaHasta = '',
}) {
  const workbook = XLSX.utils.book_new()
  const sufijoEmpresa = empresa && empresa.trim()
    ? ` — CORRESPONDIENTE A LOS CLIENTES DE: ${empresa.trim().toUpperCase()}`
    : ' — TODAS LAS CARTERAS'
  const subtituloPeriodo = `Período / Quincena: ${fechaDesde || fmtDate(totalesCartera.quincenaDesde)} al ${fechaHasta || fmtDate(totalesCartera.quincenaHasta)}`

  // 1. Pestaña: INFORME GENERAL (Consolidado)
  if (carteras.length > 0) {
    const rowsCartera = carteras.map((r) => ({
      'CARTERA': r.cartera || '',
      'BALANCE DE CAPITAL COLOCADO': Number(r.balanceCapitalColocado) || 0,
      'CAPITAL CLIENTES INACTIVOS/CANCELADOS': Number(r.capitalClientesInactivosCancelados) || 0,
      'CAPITAL ACTIVO': Number(r.capitalActivo) || 0,
      'CLIENTES ACTIVOS': Number(r.clientesActivos) || 0,
      'CLIENTES INACTIVOS': Number(r.clientesInactivos) || 0,
      'CAPITAL COBRADO DE LA QUINCENA': Number(r.capitalCobradoQuincena) || 0,
      'INTERES COBRADO DE LA QUINCENA': Number(r.interesCobradoQuincena) || 0,
      'TASA': `${Number(r.tasa) || 0}%`,
    }))
    rowsCartera.push({
      'CARTERA': 'TOTAL GENERAL',
      'BALANCE DE CAPITAL COLOCADO': Number(totalesCartera.totalBalanceCapitalColocado) || 0,
      'CAPITAL CLIENTES INACTIVOS/CANCELADOS': Number(totalesCartera.totalCapitalInactivosCancelados) || 0,
      'CAPITAL ACTIVO': Number(totalesCartera.totalCapitalActivo) || 0,
      'CLIENTES ACTIVOS': Number(totalesCartera.totalClientesActivos) || 0,
      'CLIENTES INACTIVOS': Number(totalesCartera.totalClientesInactivos) || 0,
      'CAPITAL COBRADO DE LA QUINCENA': Number(totalesCartera.totalCapitalCobradoQuincena) || 0,
      'INTERES COBRADO DE LA QUINCENA': Number(totalesCartera.totalInteresCobradoQuincena) || 0,
      'TASA': `${Number(totalesCartera.tasaPromedioPonderada) || 0}%`,
    })
    const ws = crearHojaConTitulo(
      rowsCartera,
      `INFORME GENERAL CONSOLIDADO POR CARTERA${sufijoEmpresa}`,
      subtituloPeriodo
    )
    XLSX.utils.book_append_sheet(workbook, ws, 'INFORME GENERAL')
  }

  // Helper para convertir detalle con columna CAPITAL ACTUAL ADEUDADO
  function crearFilasDetalle(lista, tot) {
    const filas = lista.map((r) => ({
      'CLASIFICACION': r.clasificacion || '',
      'EMPRESA': r.empresa || '',
      'NOMBRE': r.nombreCliente || '',
      'MONTO_PRESTAMO': Number(r.montoPrestamo) || 0,
      'CAPITAL PAGADO': Number(r.capitalPagado) || 0,
      'BALANCE ANTES DEL COBRO': Number(r.balanceAntesCobro) || 0,
      'CAPITAL COBRADO QUINCENA': Number(r.capitalCobradoQuincena) || 0,
      'INTERES COBRADO QUINCENA': Number(r.interesCobradoQuincena) || 0,
      'CAPITAL ACTUAL ADEUDADO': (r.capitalActualAdeudado && Number(r.capitalActualAdeudado) !== 0)
        ? Number(r.capitalActualAdeudado)
        : Math.max(0, (Number(r.montoPrestamo) || 0) - (Number(r.capitalPagado) || 0)),
      'TASA': Number(r.tasa) || 0,
      'COMENTARIO': r.comentario || '',
    }))
    filas.push({
      'CLASIFICACION': 'TOTAL GENERAL',
      'EMPRESA': '',
      'NOMBRE': `Total: ${tot.totalRegistros ?? lista.length}`,
      'MONTO_PRESTAMO': Number(tot.totalMontoPrestamo) || 0,
      'CAPITAL PAGADO': Number(tot.totalCapitalPagado) || 0,
      'BALANCE ANTES DEL COBRO': Number(tot.totalBalanceAntesCobro) || 0,
      'CAPITAL COBRADO QUINCENA': Number(tot.totalCapitalCobradoQuincena) || 0,
      'INTERES COBRADO QUINCENA': Number(tot.totalInteresCobradoQuincena) || 0,
      'CAPITAL ACTUAL ADEUDADO': (tot.totalCapitalActualAdeudado && Number(tot.totalCapitalActualAdeudado) !== 0)
        ? Number(tot.totalCapitalActualAdeudado)
        : Math.max(0, (Number(tot.totalMontoPrestamo) || 0) - (Number(tot.totalCapitalPagado) || 0)),
      'TASA': Number(tot.tasaPromedio) || 0,
      'COMENTARIO': '',
    })
    return filas
  }

  // 2. Pestaña: NUEVOS
  if (nuevos.length > 0) {
    const wsNuevos = crearHojaConTitulo(
      crearFilasDetalle(nuevos, totalesNuevos),
      `INFORME DE CLIENTES NUEVOS DEL PERÍODO${sufijoEmpresa}`,
      subtituloPeriodo
    )
    XLSX.utils.book_append_sheet(workbook, wsNuevos, 'NUEVOS')
  }

  // 3. Pestaña: REENGANCHES
  if (reenganches.length > 0) {
    const wsReeng = crearHojaConTitulo(
      crearFilasDetalle(reenganches, totalesReenganches),
      `INFORME DE CLIENTES REENGANCHADOS DEL PERÍODO${sufijoEmpresa}`,
      subtituloPeriodo
    )
    XLSX.utils.book_append_sheet(workbook, wsReeng, 'REENGANCHES')
  }

  // 4. Pestaña: CANCELADOS
  if (cancelados.length > 0) {
    const wsCanc = crearHojaConTitulo(
      crearFilasDetalle(cancelados, totalesCancelados),
      `INFORME DE PRÉSTAMOS CANCELADOS DEL PERÍODO${sufijoEmpresa}`,
      subtituloPeriodo
    )
    XLSX.utils.book_append_sheet(workbook, wsCanc, 'CANCELADOS')
  }

  // 5. Pestaña: DETALLE GENERAL
  if (detalleTodos.length > 0) {
    const wsDet = crearHojaConTitulo(
      crearFilasDetalle(detalleTodos, totalesDetalleTodos),
      `INFORME DETALLE COMPLETO DE CLIENTES${sufijoEmpresa}`,
      subtituloPeriodo
    )
    XLSX.utils.book_append_sheet(workbook, wsDet, 'DETALLE COMPLETO')
  }

  // 6. Pestaña: CARTERA EN MORA (Por Tramos y Compañía)
  if (carteraMora.length > 0) {
    const rowsMora = carteraMora.map((c) => ({
      'CARTERA / EMPRESA': c.cartera,
      'CLIENTES EN MORA': Number(c.totalClientesMora) || 0,
      'PRÉSTAMOS EN MORA': Number(c.totalPrestamosMora) || 0,
      'MORA 30 DÍAS': Number(c.capitalMora30Dias) || 0,
      'LEGAL 60 DÍAS': Number(c.capitalMora60DiasLegal) || 0,
      'MORA 90+ DÍAS': Number(c.capitalMora90MasDias) || 0,
      'TOTAL CAPITAL EN MORA': Number(c.totalCapitalMora) || 0,
      'OTROS CARGOS (INT/MORA)': Number(c.otrosCargosMora) || 0,
      'TOTAL DEUDA EN MORA': Number(c.totalDeudaMora) || 0,
    }))
    rowsMora.push({
      'CARTERA / EMPRESA': 'TOTAL GENERAL',
      'CLIENTES EN MORA': Number(totalesMora.totalClientesMora) || 0,
      'PRÉSTAMOS EN MORA': Number(totalesMora.totalPrestamosMora) || 0,
      'MORA 30 DÍAS': Number(totalesMora.totalCapitalMora30Dias) || 0,
      'LEGAL 60 DÍAS': Number(totalesMora.totalCapitalMora60DiasLegal) || 0,
      'MORA 90+ DÍAS': Number(totalesMora.totalCapitalMora90MasDias) || 0,
      'TOTAL CAPITAL EN MORA': Number(totalesMora.totalCapitalMora) || 0,
      'OTROS CARGOS (INT/MORA)': (Number(totalesMora.totalInteresVencido) || 0) + (Number(totalesMora.totalMoraPendiente) || 0),
      'TOTAL DEUDA EN MORA': Number(totalesMora.totalDeudaMora) || 0,
    })
    const wsMora = crearHojaConTitulo(
      rowsMora,
      `INFORME DE CARTERA EN MORA POR TRAMOS Y COMPAÑÍA${sufijoEmpresa}`,
      subtituloPeriodo
    )
    XLSX.utils.book_append_sheet(workbook, wsMora, 'CARTERA EN MORA')
  }

  XLSX.writeFile(workbook, `${nombreArchivo}_${new Date().toISOString().slice(0, 10)}.xlsx`)
}

/**
 * 6. Exporta los Indicadores y Gráfico del Dashboard a Excel
 */
export function exportarDashboardExcel(kpis, cobrosPorMes = []) {
  if (!kpis) return

  const workbook = XLSX.utils.book_new()

  // Hoja 1: Indicadores KPI
  const kpiData = [
    { 'Métrica / Indicador': 'Cartera Activa (Capital Pendiente)', 'Valor': Number(kpis.capitalPendiente) || 0, 'Unidad': 'DOP' },
    { 'Métrica / Indicador': 'Préstamos Activos en Cartera', 'Valor': Number(kpis.totalPrestamos) || 0, 'Unidad': 'Préstamos' },
    { 'Métrica / Indicador': 'Capital Original Colocado (Activo)', 'Valor': Number(kpis.capitalOriginal) || 0, 'Unidad': 'DOP' },
    { 'Métrica / Indicador': 'Cobrado Este Mes (Total Pagado)', 'Valor': Number(kpis.totalCobradoMes) || 0, 'Unidad': 'DOP' },
    { 'Métrica / Indicador': 'Capital Cobrado en el Mes', 'Valor': Number(kpis.capitalCobradoMes) || 0, 'Unidad': 'DOP' },
    { 'Métrica / Indicador': 'Interés Cobrado en el Mes', 'Valor': Number(kpis.interesCobradoMes) || 0, 'Unidad': 'DOP' },
    { 'Métrica / Indicador': 'Mora Cobrada en el Mes', 'Valor': Number(kpis.moraCobradaMes) || 0, 'Unidad': 'DOP' },
    { 'Métrica / Indicador': 'Recibos Emitidos en el Mes', 'Valor': Number(kpis.recibosMes) || 0, 'Unidad': 'Recibos' },
    { 'Métrica / Indicador': 'Préstamos Atrasados (En Mora)', 'Valor': Number(kpis.prestamosAtrasados) || 0, 'Unidad': 'Préstamos' },
    { 'Métrica / Indicador': 'Tasa de Mora Global', 'Valor': Number(kpis.tasaMora) || 0, 'Unidad': '%' },
    { 'Métrica / Indicador': 'Intereses Pendientes por Cobrar', 'Valor': Number(kpis.interesesPendientes) || 0, 'Unidad': 'DOP' },
    { 'Métrica / Indicador': 'Moras Pendientes por Cobrar', 'Valor': Number(kpis.morasPendientes) || 0, 'Unidad': 'DOP' },
    { 'Métrica / Indicador': 'Período Evaluado', 'Valor': `${fmtDate(kpis.periodoInicio)} al ${fmtDate(kpis.periodoFin)}`, 'Unidad': 'Fecha' },
  ]
  const wsKPI = crearHojaConTitulo(
    kpiData,
    'INFORME EJECUTIVO DE INDICADORES FINANCIEROS (DASHBOARD)',
    `Período: ${fmtDate(kpis.periodoInicio)} al ${fmtDate(kpis.periodoFin)}`
  )
  XLSX.utils.book_append_sheet(workbook, wsKPI, 'Resumen KPIs')

  // Hoja 2: Histórico de Cobros por Mes (Datos del Gráfico)
  if (cobrosPorMes && cobrosPorMes.length > 0) {
    const cobrosData = cobrosPorMes.map((c) => ({
      'Mes': c.mesEtiqueta || fmtDate(c.mesFecha),
      'Capital Cobrado': Number(c.capitalCobrado) || 0,
      'Interés Cobrado': Number(c.interesCobrado) || 0,
      'Mora Cobrada': Number(c.moraCobrada) || 0,
      'Total Cobrado': Number(c.totalCobrado) || 0,
      'Cantidad Recibos': Number(c.cantidadRecibos) || 0,
    }))

    // Totales de la serie
    const totCap = cobrosPorMes.reduce((acc, c) => acc + (Number(c.capitalCobrado) || 0), 0)
    const totInt = cobrosPorMes.reduce((acc, c) => acc + (Number(c.interesCobrado) || 0), 0)
    const totMor = cobrosPorMes.reduce((acc, c) => acc + (Number(c.moraCobrada) || 0), 0)
    const totTot = cobrosPorMes.reduce((acc, c) => acc + (Number(c.totalCobrado) || 0), 0)
    const totRec = cobrosPorMes.reduce((acc, c) => acc + (Number(c.cantidadRecibos) || 0), 0)

    cobrosData.push({
      'Mes': 'TOTAL HISTÓRICO',
      'Capital Cobrado': totCap,
      'Interés Cobrado': totInt,
      'Mora Cobrada': totMor,
      'Total Cobrado': totTot,
      'Cantidad Recibos': totRec,
    })

    const wsCobros = crearHojaConTitulo(
      cobrosData,
      'HISTÓRICO MENSUAL DE COBROS (ÚLTIMOS 12 MESES)',
      `Período Actual: ${fmtDate(kpis.periodoInicio)} al ${fmtDate(kpis.periodoFin)}`
    )
    XLSX.utils.book_append_sheet(workbook, wsCobros, 'Cobros por Mes')
  }

  XLSX.writeFile(workbook, `Dashboard_Financiero_SADE_${new Date().toISOString().slice(0, 10)}.xlsx`)
}

/**
 * 7. Exporta el Informe Ejecutivo del Dashboard a PDF (Tarjetas + Tabla Histórica de Cobros)
 */
export function exportarDashboardPDF(kpis, cobrosPorMes = []) {
  if (!kpis) return

  const doc = new jsPDF('portrait', 'pt', 'letter')

  // Encabezado institucional
  doc.setFontSize(16)
  doc.setTextColor(30, 58, 95)
  doc.text('SADE WEB — INFORME EJECUTIVO FINANCIERO', 40, 40)

  doc.setFontSize(10)
  doc.setTextColor(80)
  doc.text(`Período Activo: ${fmtDate(kpis.periodoInicio)} al ${fmtDate(kpis.periodoFin)}`, 40, 58)
  doc.text(`Fecha y Hora de Emisión: ${new Date().toLocaleDateString('es-DO')} ${new Date().toLocaleTimeString('es-DO')}`, 40, 72)

  // Resumen Ejecutivo en Grid (KPI Cards)
  const kpiRows = [
    ['CARTERA ACTIVA (CAPITAL PENDIENTE)', fmtMoney(kpis.capitalPendiente), `${kpis.totalPrestamos ?? 0} préstamos activos`],
    ['TOTAL COBRADO ESTE MES', fmtMoney(kpis.totalCobradoMes), `${kpis.recibosMes ?? 0} recibos emitidos`],
    ['PRÉSTAMOS ATRASADOS (EN MORA)', String(kpis.prestamosAtrasados ?? 0), `Mora pendiente: ${fmtMoney(kpis.morasPendientes)}`],
    ['TASA DE MORA GLOBAL', `${Number(kpis.tasaMora ?? 0).toFixed(1)}%`, `Intereses pendientes: ${fmtMoney(kpis.interesesPendientes)}`],
    ['CAPITAL ORIGINAL VIGENTE', fmtMoney(kpis.capitalOriginal), 'Base de cartera colocada activa'],
    ['CAPITAL COBRADO (MES)', fmtMoney(kpis.capitalCobradoMes), 'Retorno de capital mes actual'],
    ['INTERÉS COBRADO (MES)', fmtMoney(kpis.interesCobradoMes), 'Utilidad cobrada mes actual'],
  ]

  autoTable(doc, {
    head: [['INDICADOR FINANCIERO CLAVE', 'VALOR ACTUAL', 'DETALLE / OBSERVACIÓN']],
    body: kpiRows,
    startY: 85,
    theme: 'grid',
    styles: { fontSize: 8.5, cellPadding: 4.5 },
    headStyles: { fillColor: [30, 58, 95], textColor: [255, 255, 255], fontStyle: 'bold' },
    alternateRowStyles: { fillColor: [248, 250, 252] },
  })

  // Tabla Histórica de Cobros Mensuales (Datos de los Gráficos de Barras)
  if (cobrosPorMes && cobrosPorMes.length > 0) {
    const tableY = doc.lastAutoTable.finalY + 25
    doc.setFontSize(11)
    doc.setTextColor(30, 58, 95)
    doc.text('HISTÓRICO MENSUAL DE COBROS (ÚLTIMOS 12 MESES)', 40, tableY)

    const cobrosCols = ['MES', 'CAPITAL COBRADO', 'INTERÉS COBRADO', 'MORA COBRADA', 'TOTAL COBRADO', 'RECIBOS']
    const cobrosRows = cobrosPorMes.map((c) => [
      c.mesEtiqueta || fmtDate(c.mesFecha),
      fmtMoney(c.capitalCobrado),
      fmtMoney(c.interesCobrado),
      fmtMoney(c.moraCobrada),
      fmtMoney(c.totalCobrado),
      String(c.cantidadRecibos ?? 0),
    ])

    const totCap = cobrosPorMes.reduce((acc, c) => acc + (Number(c.capitalCobrado) || 0), 0)
    const totInt = cobrosPorMes.reduce((acc, c) => acc + (Number(c.interesCobrado) || 0), 0)
    const totMor = cobrosPorMes.reduce((acc, c) => acc + (Number(c.moraCobrada) || 0), 0)
    const totTot = cobrosPorMes.reduce((acc, c) => acc + (Number(c.totalCobrado) || 0), 0)
    const totRec = cobrosPorMes.reduce((acc, c) => acc + (Number(c.cantidadRecibos) || 0), 0)

    const footCobros = [
      'TOTAL GENERAL',
      fmtMoney(totCap),
      fmtMoney(totInt),
      fmtMoney(totMor),
      fmtMoney(totTot),
      String(totRec),
    ]

    autoTable(doc, {
      head: [cobrosCols],
      body: cobrosRows,
      foot: [footCobros],
      startY: tableY + 10,
      theme: 'grid',
      styles: { fontSize: 8, cellPadding: 4 },
      headStyles: { fillColor: [15, 118, 110], textColor: [255, 255, 255], fontStyle: 'bold' },
      footStyles: { fillColor: [30, 58, 95], textColor: [255, 255, 255], fontStyle: 'bold' },
      alternateRowStyles: { fillColor: [248, 250, 252] },
    })
  }

  doc.save(`Reporte_Ejecutivo_Dashboard_${new Date().toISOString().slice(0, 10)}.pdf`)
}

/**
 * 8. Exporta la Tabla de Cuotas de un Préstamo a Excel
 */
export function exportarCuotasExcel(cuotas = [], prestamoInfo = {}, nombreArchivo = null) {
  if (!cuotas || cuotas.length === 0) return

  const numPres = prestamoInfo.numeroPrestamo || prestamoInfo.idCxc || 'Detalle'
  const cliNom = prestamoInfo.nombreCliente || 'Cliente'

  const rows = cuotas.map((c) => ({
    '# Cuota': c.numCuota,
    'Fecha Vencimiento': fmtDate(c.fecha),
    'Balance Cuota': Number(c.balance) || 0,
    'Capital': Number(c.capital) || 0,
    'Interés': Number(c.interes) || 0,
    'Mora': Number(c.mora) || 0,
    'Estado': c.estadoCuota || c.estado || 'PENDIENTE',
  }))

  // Fila de totales
  const totBal = cuotas.reduce((s, c) => s + (Number(c.balance) || 0), 0)
  const totCap = cuotas.reduce((s, c) => s + (Number(c.capital) || 0), 0)
  const totInt = cuotas.reduce((s, c) => s + (Number(c.interes) || 0), 0)
  const totMor = cuotas.reduce((s, c) => s + (Number(c.mora) || 0), 0)

  rows.push({
    '# Cuota': 'TOTAL GENERAL',
    'Fecha Vencimiento': `${cuotas.length} cuotas`,
    'Balance Cuota': totBal,
    'Capital': totCap,
    'Interés': totInt,
    'Mora': totMor,
    'Estado': '',
  })

  const sub = `Cliente: ${cliNom} | Cédula: ${prestamoInfo.cedula || '—'} | Préstamo #${numPres} | Empresa: ${prestamoInfo.empresa || '—'}`
  const ws = crearHojaConTitulo(rows, `TABLA DE CUOTAS — PRÉSTAMO #${numPres}`, sub)
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, `Cuotas_${numPres}`)

  const filename = nombreArchivo || `Cuotas_Prestamo_${numPres}_${new Date().toISOString().slice(0, 10)}.xlsx`
  XLSX.writeFile(wb, filename)
}

/**
 * 9. Exporta la Tabla de Cuotas de un Préstamo a PDF
 */
export function exportarCuotasPDF(cuotas = [], prestamoInfo = {}, nombreArchivo = null) {
  if (!cuotas || cuotas.length === 0) return

  const numPres = prestamoInfo.numeroPrestamo || prestamoInfo.idCxc || 'Detalle'
  const cliNom = prestamoInfo.nombreCliente || 'Cliente'
  const doc = new jsPDF('portrait', 'pt', 'letter')

  // Encabezado
  doc.setFontSize(14)
  doc.setTextColor(30, 58, 95)
  doc.text('SADE WEB — TABLA DE AMORTIZACIÓN Y CUOTAS', 40, 38)

  doc.setFontSize(10)
  doc.setTextColor(50)
  doc.text(`Préstamo #${numPres}  |  Cliente: ${cliNom}  |  Cédula: ${prestamoInfo.cedula || '—'}`, 40, 54)
  doc.text(`Empresa / Cartera: ${prestamoInfo.empresa || '—'}  |  Tasa: ${prestamoInfo.tasaInteres || prestamoInfo.tasa || '—'}%  |  Capital Pendiente: ${fmtMoney(prestamoInfo.capitalBalance || 0)}`, 40, 68)

  doc.setFontSize(8.5)
  doc.setTextColor(110)
  doc.text(`Emisión: ${new Date().toLocaleDateString('es-DO')} ${new Date().toLocaleTimeString('es-DO')}  |  Total Cuotas: ${cuotas.length}`, 40, 82)

  const cols = ['#', 'VENCIMIENTO', 'BALANCE', 'CAPITAL', 'INTERÉS', 'MORA', 'ESTADO']
  const rows = cuotas.map((c) => [
    String(c.numCuota),
    fmtDate(c.fecha),
    fmtMoney(c.balance),
    fmtMoney(c.capital),
    fmtMoney(c.interes),
    fmtMoney(c.mora),
    c.estadoCuota || c.estado || 'PENDIENTE',
  ])

  const totBal = cuotas.reduce((s, c) => s + (Number(c.balance) || 0), 0)
  const totCap = cuotas.reduce((s, c) => s + (Number(c.capital) || 0), 0)
  const totInt = cuotas.reduce((s, c) => s + (Number(c.interes) || 0), 0)
  const totMor = cuotas.reduce((s, c) => s + (Number(c.mora) || 0), 0)

  const foot = [
    'TOTAL',
    `${cuotas.length} cuotas`,
    fmtMoney(totBal),
    fmtMoney(totCap),
    fmtMoney(totInt),
    fmtMoney(totMor),
    '',
  ]

  autoTable(doc, {
    head: [cols],
    body: rows,
    foot: [foot],
    startY: 94,
    theme: 'grid',
    styles: { fontSize: 8, cellPadding: 3.5 },
    headStyles: { fillColor: [30, 58, 95], textColor: [255, 255, 255], fontStyle: 'bold' },
    footStyles: { fillColor: [30, 58, 95], textColor: [255, 255, 255], fontStyle: 'bold' },
    alternateRowStyles: { fillColor: [248, 250, 252] },
  })

  const filename = nombreArchivo || `Cuotas_Prestamo_${numPres}_${new Date().toISOString().slice(0, 10)}.pdf`
  doc.save(filename)
}

/**
 * 10. Exporta el Historial de Pagos (Recibos) de un Préstamo a Excel
 */
export function exportarHistorialPagosExcel(recibos = [], prestamoInfo = {}, nombreArchivo = null) {
  if (!recibos || recibos.length === 0) return

  const numPres = prestamoInfo.numeroPrestamo || prestamoInfo.idCxc || 'Detalle'
  const cliNom = prestamoInfo.nombreCliente || 'Cliente'

  const rows = recibos.map((r) => ({
    'Recibo #': r.numeroPago,
    'Fecha de Pago': fmtDate(r.fecha),
    'Total Pagado': Number(r.totalPagado) || 0,
    'Capital Aplicado': Number(r.capital) || 0,
    'Interés Aplicado': Number(r.interes) || 0,
    'Mora Aplicada': Number(r.mora) || 0,
    'Usuario / Caja': r.usuario || '—',
  }))

  const totTot = recibos.reduce((s, r) => s + (Number(r.totalPagado) || 0), 0)
  const totCap = recibos.reduce((s, r) => s + (Number(r.capital) || 0), 0)
  const totInt = recibos.reduce((s, r) => s + (Number(r.interes) || 0), 0)
  const totMor = recibos.reduce((s, r) => s + (Number(r.mora) || 0), 0)

  rows.push({
    'Recibo #': 'TOTAL COBRADO',
    'Fecha de Pago': `${recibos.length} recibos`,
    'Total Pagado': totTot,
    'Capital Aplicado': totCap,
    'Interés Aplicado': totInt,
    'Mora Aplicada': totMor,
    'Usuario / Caja': '',
  })

  const sub = `Cliente: ${cliNom} | Cédula: ${prestamoInfo.cedula || '—'} | Préstamo #${numPres} | Total Pagado: ${fmtMoney(totTot)}`
  const ws = crearHojaConTitulo(rows, `HISTORIAL DE PAGOS Y RECIBOS — PRÉSTAMO #${numPres}`, sub)
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, `Pagos_${numPres}`)

  const filename = nombreArchivo || `Historial_Pagos_Prestamo_${numPres}_${new Date().toISOString().slice(0, 10)}.xlsx`
  XLSX.writeFile(wb, filename)
}

/**
 * 11. Exporta el Historial de Pagos (Recibos) de un Préstamo a PDF
 */
export function exportarHistorialPagosPDF(recibos = [], prestamoInfo = {}, nombreArchivo = null) {
  if (!recibos || recibos.length === 0) return

  const numPres = prestamoInfo.numeroPrestamo || prestamoInfo.idCxc || 'Detalle'
  const cliNom = prestamoInfo.nombreCliente || 'Cliente'
  const doc = new jsPDF('portrait', 'pt', 'letter')

  doc.setFontSize(14)
  doc.setTextColor(30, 58, 95)
  doc.text('SADE WEB — HISTORIAL DE PAGOS Y RECIBOS', 40, 38)

  doc.setFontSize(10)
  doc.setTextColor(50)
  doc.text(`Préstamo #${numPres}  |  Cliente: ${cliNom}  |  Cédula: ${prestamoInfo.cedula || '—'}`, 40, 54)
  doc.text(`Empresa / Cartera: ${prestamoInfo.empresa || '—'}  |  Total Recibos Emitidos: ${recibos.length}`, 40, 68)

  doc.setFontSize(8.5)
  doc.setTextColor(110)
  doc.text(`Emisión: ${new Date().toLocaleDateString('es-DO')} ${new Date().toLocaleTimeString('es-DO')}`, 40, 82)

  const cols = ['RECIBO #', 'FECHA PAGO', 'TOTAL PAGADO', 'CAPITAL', 'INTERÉS', 'MORA', 'OPERADOR']
  const rows = recibos.map((r) => [
    `#${r.numeroPago}`,
    fmtDate(r.fecha),
    fmtMoney(r.totalPagado),
    fmtMoney(r.capital),
    fmtMoney(r.interes),
    fmtMoney(r.mora),
    r.usuario || '—',
  ])

  const totTot = recibos.reduce((s, r) => s + (Number(r.totalPagado) || 0), 0)
  const totCap = recibos.reduce((s, r) => s + (Number(r.capital) || 0), 0)
  const totInt = recibos.reduce((s, r) => s + (Number(r.interes) || 0), 0)
  const totMor = recibos.reduce((s, r) => s + (Number(r.mora) || 0), 0)

  const foot = [
    'TOTAL',
    `${recibos.length} recibos`,
    fmtMoney(totTot),
    fmtMoney(totCap),
    fmtMoney(totInt),
    fmtMoney(totMor),
    '',
  ]

  autoTable(doc, {
    head: [cols],
    body: rows,
    foot: [foot],
    startY: 94,
    theme: 'grid',
    styles: { fontSize: 8, cellPadding: 4 },
    headStyles: { fillColor: [15, 118, 110], textColor: [255, 255, 255], fontStyle: 'bold' },
    footStyles: { fillColor: [30, 58, 95], textColor: [255, 255, 255], fontStyle: 'bold' },
    alternateRowStyles: { fillColor: [248, 250, 252] },
  })

  const filename = nombreArchivo || `Historial_Pagos_Prestamo_${numPres}_${new Date().toISOString().slice(0, 10)}.pdf`
  doc.save(filename)
}

/**
 * 12. Exporta el Reporte Especializado de Clientes Atrasados / Mora por Tramos a Excel (2 Hojas)
 */
export function exportarReporteClientesAtrasadosExcel({
  carteras = [],
  clientes = [],
  totales = {},
  nombreArchivo = 'Reporte_Cartera_En_Mora',
  titulo = 'INFORME DE CARTERA EN MORA POR TRAMOS Y COMPAÑÍA',
  fechaCorte = null,
}) {
  const wb = XLSX.utils.book_new()
  const fechaStr = fechaCorte ? fmtDate(fechaCorte) : fmtDate(new Date())

  // Hoja 1: Resumen por Compañía / Cartera
  const carterasRows = carteras.map((c) => ({
    'Cartera / Empresa': c.cartera,
    'Clientes en Mora': c.totalClientesMora,
    'Préstamos en Mora': c.totalPrestamosMora,
    'Mora 30 Días (RD$)': Number(c.capitalMora30Dias) || 0,
    'Legal 60 Días (RD$)': Number(c.capitalMora60DiasLegal) || 0,
    'Mora 90+ Días (RD$)': Number(c.capitalMora90MasDias) || 0,
    'Total Capital en Mora (RD$)': Number(c.totalCapitalMora) || 0,
    'Otros Cargos (Int/Mora)': Number(c.otrosCargosMora) || 0,
    'Total Deuda en Mora (RD$)': Number(c.totalDeudaMora) || 0,
  }))

  carterasRows.push({
    'Cartera / Empresa': 'TOTAL GENERAL',
    'Clientes en Mora': totales.totalClientesMora || 0,
    'Préstamos en Mora': totales.totalPrestamosMora || 0,
    'Mora 30 Días (RD$)': Number(totales.totalCapitalMora30Dias) || 0,
    'Legal 60 Días (RD$)': Number(totales.totalCapitalMora60DiasLegal) || 0,
    'Mora 90+ Días (RD$)': Number(totales.totalCapitalMora90MasDias) || 0,
    'Total Capital en Mora (RD$)': Number(totales.totalCapitalMora) || 0,
    'Otros Cargos (Int/Mora)': (Number(totales.totalInteresVencido) || 0) + (Number(totales.totalMoraPendiente) || 0),
    'Total Deuda en Mora (RD$)': Number(totales.totalDeudaMora) || 0,
  })

  const wsCarteras = crearHojaConTitulo(
    carterasRows,
    titulo,
    `Fecha de Corte: ${fechaStr}  |  Total Carteras con Mora: ${carteras.length}`
  )
  XLSX.utils.book_append_sheet(wb, wsCarteras, 'Resumen por Compañía')

  // Hoja 2: Detalle Individual de Clientes en Mora
  const clientesRows = clientes.map((cl) => ({
    'ID Cliente': cl.idCliente,
    'Nombre del Cliente': cl.nombreCliente,
    'Cédula': cl.cedula || '—',
    'Teléfono': cl.telefono || '—',
    'Empresa / Cartera': cl.empresa || '—',
    'Préstamo #': cl.numeroPrestamo,
    'Días Atraso': cl.diasAtraso,
    'Tramo de Mora': cl.tramoMora,
    'Cuotas Vencidas': cl.cuotasVencidas,
    '1er Vencimiento': fmtDate(cl.primeraFechaVenc),
    'Capital Vencido (RD$)': Number(cl.capitalVencido) || 0,
    'Interés Vencido (RD$)': Number(cl.interesVencido) || 0,
    'Mora Pendiente (RD$)': Number(cl.moraPendiente) || 0,
    'Total Vencido (RD$)': Number(cl.totalVencido) || 0,
    'Saldo Capital Total (RD$)': Number(cl.saldoCapital) || 0,
    'Tasa': `${cl.tasa}%`,
  }))

  const wsClientes = crearHojaConTitulo(
    clientesRows,
    'DETALLE INDIVIDUAL DE CLIENTES EN MORA',
    `Fecha de Corte: ${fechaStr}  |  Total Clientes Atrasados: ${clientes.length}`
  )
  XLSX.utils.book_append_sheet(wb, wsClientes, 'Detalle Clientes Atrasados')

  XLSX.writeFile(wb, `${nombreArchivo}_${new Date().toISOString().slice(0, 10)}.xlsx`)
}

/**
 * 13. Exporta el Reporte Especializado de Clientes Atrasados / Mora por Tramos a PDF
 */
export function exportarReporteClientesAtrasadosPDF({
  carteras = [],
  clientes = [],
  totales = {},
  titulo = 'INFORME DE CARTERA EN MORA POR TRAMOS Y COMPAÑÍA',
  nombreArchivo = 'Reporte_Cartera_En_Mora',
  fechaCorte = null,
}) {
  const doc = new jsPDF('landscape', 'pt', 'letter')
  const fechaStr = fechaCorte ? fmtDate(fechaCorte) : fmtDate(new Date())

  // Encabezado
  doc.setFontSize(14)
  doc.setTextColor(30, 58, 95)
  doc.text('SADE WEB — SISTEMA DE GESTIÓN FINANCIERA', 40, 36)

  doc.setFontSize(11)
  doc.setTextColor(180, 40, 40)
  doc.text(titulo.toUpperCase(), 40, 52)

  doc.setFontSize(9)
  doc.setTextColor(80)
  doc.text(
    `Fecha de Corte: ${fechaStr}  |  Capital en Mora: ${fmtMoney(totales.totalCapitalMora)}  |  Clientes Atrasados: ${totales.totalClientesMora || 0}`,
    40,
    66
  )

  // Tabla 1: Resumen por Compañía y Tramos de Mora
  const headCols = [
    'CARTERA / EMPRESA',
    'CLI.',
    'PRÉST.',
    'MORA 30 DÍAS',
    'LEGAL 60 DÍAS',
    'MORA 90+ DÍAS',
    'CAPITAL EN MORA',
    'OTROS CARGOS',
    'TOTAL EN MORA',
  ]

  const bodyRows = carteras.map((c) => [
    c.cartera,
    String(c.totalClientesMora),
    String(c.totalPrestamosMora),
    fmtMoney(c.capitalMora30Dias),
    fmtMoney(c.capitalMora60DiasLegal),
    fmtMoney(c.capitalMora90MasDias),
    fmtMoney(c.totalCapitalMora),
    fmtMoney(c.otrosCargosMora),
    fmtMoney(c.totalDeudaMora),
  ])

  const footCols = [
    'TOTAL GENERAL',
    String(totales.totalClientesMora || 0),
    String(totales.totalPrestamosMora || 0),
    fmtMoney(totales.totalCapitalMora30Dias),
    fmtMoney(totales.totalCapitalMora60DiasLegal),
    fmtMoney(totales.totalCapitalMora90MasDias),
    fmtMoney(totales.totalCapitalMora),
    fmtMoney((Number(totales.totalInteresVencido) || 0) + (Number(totales.totalMoraPendiente) || 0)),
    fmtMoney(totales.totalDeudaMora),
  ]

  autoTable(doc, {
    head: [headCols],
    body: bodyRows,
    foot: [footCols],
    startY: 80,
    theme: 'grid',
    styles: { fontSize: 7.5, cellPadding: 3.5 },
    headStyles: { fillColor: [180, 40, 40], textColor: [255, 255, 255], fontStyle: 'bold' },
    footStyles: { fillColor: [30, 58, 95], textColor: [255, 255, 255], fontStyle: 'bold' },
    alternateRowStyles: { fillColor: [248, 250, 252] },
  })

  // Tabla 2: Detalle de Clientes en Mora (en página nueva o continuación)
  if (clientes && clientes.length > 0) {
    doc.addPage()
    doc.setFontSize(12)
    doc.setTextColor(30, 58, 95)
    doc.text('DETALLE INDIVIDUAL DE CLIENTES EN ESTADO DE MORA', 40, 36)

    doc.setFontSize(8.5)
    doc.setTextColor(100)
    doc.text(`Fecha de Corte: ${fechaStr}  |  Total Clientes: ${clientes.length}`, 40, 50)

    const cliCols = [
      'CLIENTE',
      'CÉDULA',
      'TELÉFONO',
      'EMPRESA',
      'PRÉSTAMO',
      'DÍAS',
      'TRAMO',
      'CUOTAS',
      'CAPITAL VENCIDO',
      'INTERÉS',
      'TOTAL VENCIDO',
    ]

    const cliRows = clientes.map((cl) => [
      cl.nombreCliente,
      cl.cedula || '—',
      cl.telefono || '—',
      (cl.empresa || '—').slice(0, 22),
      `#${cl.numeroPrestamo}`,
      String(cl.diasAtraso),
      cl.tramoMora,
      String(cl.cuotasVencidas),
      fmtMoney(cl.capitalVencido),
      fmtMoney(cl.interesVencido),
      fmtMoney(cl.totalVencido),
    ])

    autoTable(doc, {
      head: [cliCols],
      body: cliRows,
      startY: 60,
      theme: 'grid',
      styles: { fontSize: 7, cellPadding: 3 },
      headStyles: { fillColor: [30, 58, 95], textColor: [255, 255, 255], fontStyle: 'bold' },
      alternateRowStyles: { fillColor: [248, 250, 252] },
    })
  }

  doc.save(`${nombreArchivo}_${new Date().toISOString().slice(0, 10)}.pdf`)
}

/**
 * 14. Exporta el Top de Empresas / Distribución de Cartera a PDF
 */
export function exportarTopEmpresasPDF(porEmpresa = [], titulo = 'DISTRIBUCIÓN Y TOP DE EMPRESAS / CARTERAS') {
  if (!porEmpresa || porEmpresa.length === 0) return

  const doc = new jsPDF('portrait', 'pt', 'letter')

  doc.setFontSize(14)
  doc.setTextColor(30, 58, 95)
  doc.text('SADE WEB — SISTEMA DE GESTIÓN FINANCIERA', 40, 38)

  doc.setFontSize(11)
  doc.setTextColor(50)
  doc.text(titulo.toUpperCase(), 40, 54)

  const totCli = porEmpresa.reduce((s, e) => s + (Number(e.totalClientes) || 0), 0)
  const totNue = porEmpresa.reduce((s, e) => s + (Number(e.nuevos) || 0), 0)
  const totRee = porEmpresa.reduce((s, e) => s + (Number(e.reenganchados) || 0), 0)
  const totMor = porEmpresa.reduce((s, e) => s + (Number(e.enMora) || 0), 0)
  const totCar = porEmpresa.reduce((s, e) => s + (Number(e.cartera) || 0), 0)

  doc.setFontSize(8.5)
  doc.setTextColor(100)
  doc.text(
    `Fecha de Emisión: ${new Date().toLocaleDateString('es-DO')} ${new Date().toLocaleTimeString('es-DO')}  |  Total Empresas: ${porEmpresa.length}  |  Total Clientes: ${totCli}`,
    40,
    68
  )

  const cols = [
    'POS.',
    'EMPRESA / CARTERA',
    'CLIENTES',
    'NUEVOS',
    'REENGANCHADOS',
    'EN MORA',
    'CARTERA (RD$)',
    '% PART.',
  ]

  const rows = porEmpresa.map((e, idx) => {
    const pct = totCli > 0 ? ((Number(e.totalClientes) || 0) / totCli) * 100 : 0
    return [
      `#${idx + 1}`,
      e.empresa || '(Sin empresa)',
      String(e.totalClientes ?? 0),
      String(e.nuevos ?? 0),
      String(e.reenganchados ?? 0),
      String(e.enMora ?? 0),
      fmtMoney(e.cartera),
      `${pct.toFixed(1)}%`,
    ]
  })

  const foot = [
    'TOTAL',
    `${porEmpresa.length} empresas`,
    String(totCli),
    String(totNue),
    String(totRee),
    String(totMor),
    fmtMoney(totCar),
    '100.0%',
  ]

  autoTable(doc, {
    head: [cols],
    body: rows,
    foot: [foot],
    startY: 80,
    theme: 'grid',
    styles: { fontSize: 8, cellPadding: 4 },
    headStyles: { fillColor: [30, 58, 95], textColor: [255, 255, 255], fontStyle: 'bold' },
    footStyles: { fillColor: [30, 58, 95], textColor: [255, 255, 255], fontStyle: 'bold' },
    alternateRowStyles: { fillColor: [248, 250, 252] },
  })

  doc.save(`Top_Empresas_SADE_${new Date().toISOString().slice(0, 10)}.pdf`)
}

