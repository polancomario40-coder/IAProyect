const XLSX = require('xlsx');

/**
 * Convierte número de serie de fecha de Excel a objeto Date de JavaScript.
 */
function parseExcelDate(excelVal) {
  if (!excelVal) return null;
  if (excelVal instanceof Date) return excelVal;
  if (typeof excelVal === 'number') {
    return new Date(Math.round((excelVal - 25569) * 86400 * 1000));
  }
  const parsed = new Date(excelVal);
  return isNaN(parsed.getTime()) ? null : parsed;
}

/**
 * Parsea un archivo Excel de Cut Ticket (Buffer o ruta de archivo).
 */
function parseCutTicket(fileSource) {
  let workbook;
  if (Buffer.isBuffer(fileSource)) {
    workbook = XLSX.read(fileSource, { type: 'buffer' });
  } else {
    workbook = XLSX.readFile(fileSource);
  }

  const sheetName = workbook.SheetNames[0];
  const worksheet = workbook.Sheets[sheetName];
  if (!worksheet) {
    throw new Error('El archivo Excel no contiene hojas de cálculo.');
  }

  // Convertir a matriz de celdas
  const sheetData = XLSX.utils.sheet_to_json(worksheet, { header: 1, defval: '' });

  const ticket = {
    cutNumber: '',
    orderNumber: '',
    style: '',
    customer: '',
    gerberModel: '',
    folder: '',
    fabric: '',
    fabricDesc: '',
    mill: '',
    cuttableWidth: '',
    totalUnits: 0,
    orderDate: null,
    cutDate: null,
    requireShipDate: null,
    specialInstructions: [],
    markers: [],
    sizesSummary: []
  };

  const knownSizes = ['XXS', 'XS', 'S', 'M', 'L', 'XL', '2XL', '3XL', '4XL', '5XL', '6XL', '7XL', '8XL', '9XL', '10XL', '11XL'];
  let markerHeaderRowIdx = -1;
  let cutRowIdx = -1;

  // 1. Recorrer celdas para extraer encabezados principales
  for (let r = 0; r < Math.min(sheetData.length, 50); r++) {
    const row = sheetData[r] || [];
    for (let c = 0; c < row.length; c++) {
      const cellText = String(row[c] || '').trim();

      // Gerber Model
      if (/Gerber Model/i.test(cellText)) {
        // Puede venir como 'Gerber Model' en A y valor en B, o 'Gerber Model: 82517...' en una sola celda
        if (cellText.includes(':')) {
          ticket.gerberModel = cellText.split(':')[1].trim();
        } else {
          ticket.gerberModel = String(row[c + 1] || '').trim();
        }
      }
      // FOLDER
      else if (/^FOLDER:/i.test(cellText)) {
        ticket.folder = String(row[c + 1] || '').trim();
      }
      // Fabric
      else if (/^Fabric:$/i.test(cellText)) {
        ticket.fabric = String(row[c + 1] || '').trim();
      }
      // Fabric Desc
      else if (/^Fabric Desc/i.test(cellText)) {
        ticket.fabricDesc = String(row[c + 1] || '').trim();
      }
      // Mill
      else if (/^Mill:$/i.test(cellText)) {
        ticket.mill = String(row[c + 1] || '').trim();
      }
      // Date(Fecha)
      else if (/Date\(Fecha\):/i.test(cellText)) {
        ticket.orderDate = parseExcelDate(row[c + 1]);
      }
      // Cut Date
      else if (/^Cut Date:/i.test(cellText)) {
        ticket.cutDate = parseExcelDate(row[c + 1]);
      }
      // CUTTABLE WIDTH
      else if (/CUTTABLE WIDTH/i.test(cellText)) {
        ticket.cuttableWidth = String(row[c + 1] || '').trim();
      }
      // CUSTOMER
      else if (/CUSTOMER:/i.test(cellText)) {
        for (let nextC = c + 1; nextC < row.length; nextC++) {
          const val = String(row[nextC] || '').trim();
          if (val && !/Failed|Actual|Missing|Remain|WIDTH/i.test(val)) {
            ticket.customer = val;
            break;
          }
        }
      }
      // TOTAL UNITS
      else if (/TOTAL UNITS:/i.test(cellText)) {
        ticket.totalUnits = parseInt(row[c + 1], 10) || 0;
      }
      // REQUIRE SHIP DATE
      else if (/REQUIRE SHIP DATE:/i.test(cellText)) {
        ticket.requireShipDate = parseExcelDate(row[c + 1]);
      }

      // Detectar la fila de títulos de la tabla de trazos
      if ((/^\(Estilo\)$/i.test(cellText) || /^Style$/i.test(cellText)) && markerHeaderRowIdx === -1) {
        markerHeaderRowIdx = r;
      }

      // Buscar Cut Number si tiene formato MTO-xxx
      if (/^MTO-\d+/i.test(cellText) && !ticket.cutNumber) {
        ticket.cutNumber = cellText;
        cutRowIdx = r;
        if (!ticket.style && row[c - 1]) {
          ticket.style = String(row[c - 1]).trim();
        }
      }
      // Buscar Cut Number si tiene formato ORDxxx o PO-xxx
      else if (/^(ORD\d+|PO[-\s]?\d+)/i.test(cellText) && !ticket.cutNumber) {
        ticket.cutNumber = cellText;
        ticket.orderNumber = cellText;
        cutRowIdx = r;
        if (!ticket.style && row[c - 1]) {
          ticket.style = String(row[c - 1]).trim();
        }
      }
    }

    // Capturar instrucciones especiales (habitualmente en columna H o I)
    for (let colIdx = 7; colIdx <= 10; colIdx++) {
      const specInst = String(row[colIdx] || '').trim();
      if (specInst && specInst !== '-' && !/SPECIAL INSTRUCTION/i.test(specInst) && !ticket.specialInstructions.includes(specInst)) {
        // Filtrar números aislados o etiquetas de resumen
        if (!/^\d+(\.\d+)?$/.test(specInst) && !/Actual|Failed|Missing|Remain/i.test(specInst)) {
          ticket.specialInstructions.push(specInst);
        }
      }
    }
  }

  // 1.1 Si no se detectó el corte por prefijo MTO/ORD, buscar en la fila después del encabezado de Estilo/Corte
  if (!ticket.cutNumber && markerHeaderRowIdx !== -1) {
    for (let r = markerHeaderRowIdx + 1; r < Math.min(sheetData.length, markerHeaderRowIdx + 4); r++) {
      const row = sheetData[r] || [];
      const colA = String(row[0] || '').trim();
      const colB = String(row[1] || '').trim();

      if (colA && colA !== '(Estilo)' && colA !== 'Style' && !ticket.style) {
        ticket.style = colA;
      }

      if (colB && colB !== '(Corte)' && colB !== 'Cut' && !ticket.cutNumber) {
        ticket.cutNumber = colB;
        if (/^ORD/i.test(colB)) {
          ticket.orderNumber = colB;
        }
        break;
      }
    }
  }

  // 2. Extraer marcadores y tallas
  // Si markerHeaderRowIdx se detectó, revisamos la fila de columnas de tallas
  let sizeHeaderRow = [];
  let sizeHeaderRowIdx = -1;

  for (let r = 10; r < Math.min(sheetData.length, 25); r++) {
    const row = sheetData[r] || [];
    const sizeMatches = row.filter(cell => knownSizes.includes(String(cell || '').trim().toUpperCase()));
    if (sizeMatches.length >= 3) {
      sizeHeaderRow = row;
      sizeHeaderRowIdx = r;
      break;
    }
  }

  if (sizeHeaderRowIdx !== -1) {
    // Detectar todas las columnas de tallas
    const detectedCols = [];
    for (let c = 0; c < sizeHeaderRow.length; c++) {
      const val = String(sizeHeaderRow[c] || '').trim().toUpperCase();
      if (knownSizes.includes(val)) {
        detectedCols.push({ colIndex: c, size: val });
      }
    }

    // En la plantilla estándar hay dos grupos: el primer grupo es el Ratio, el segundo grupo es Unidades Cortadas
    const half = Math.floor(detectedCols.length / 2);
    const ratioCols = detectedCols.slice(0, half);
    const unitsCols = detectedCols.slice(half);

    // Las filas de marcadores empiezan después de sizeHeaderRowIdx
    for (let r = sizeHeaderRowIdx + 1; r < sheetData.length; r++) {
      const row = sheetData[r] || [];
      const colA = String(row[0] || '').trim();
      const colB = String(row[1] || '').trim();
      const colC = String(row[2] || '').trim();
      const colD = String(row[3] || '').trim();

      if (/TOTAL UNITS/i.test(colA)) break;

      // Un marcador suele estar en col C (ej. "M199-" o "25NE-") y col D ("6466" o "615-")
      let markerName = `${colC} ${colD}`.trim();
      if (!markerName || markerName === '#') {
        // Podría ser solo col C
        markerName = colC;
      }

      if (!markerName || markerName === '#' || markerName === '0') continue;

      // Plies / Lienzos (suele estar entre col 7 y 9)
      let plies = 0;
      let markerLength = 0;
      let eff = 0;

      for (let c = 4; c <= 9; c++) {
        const val = row[c];
        if (typeof val === 'number') {
          if (val > 50 && val <= 100 && eff === 0) eff = val; // Eff %
          else if (val > 0 && val < 50 && markerLength === 0) markerLength = val; // Length
          else if (Number.isInteger(val) && val > 0 && plies === 0) plies = val; // Plies
        }
      }

      // Si col I (índice 8) o H (índice 7) tiene plies como entero
      const pliesCandidate = parseInt(row[8], 10) || parseInt(row[7], 10);
      if (pliesCandidate > 0) plies = pliesCandidate;

      const markerObj = {
        markerName: markerName.replace(/\s+/g, ' '),
        fabricWidth: ticket.cuttableWidth,
        markerLength: markerLength,
        efficiency: eff,
        plies: plies,
        sizeBreakdown: []
      };

      // Extraer tallas cortadas para este marcador
      for (let i = 0; i < unitsCols.length; i++) {
        const uCol = unitsCols[i];
        const rCol = ratioCols[i];

        const units = parseInt(row[uCol.colIndex], 10) || 0;
        const ratio = rCol ? (parseInt(row[rCol.colIndex], 10) || 0) : 0;

        if (units > 0 || ratio > 0) {
          markerObj.sizeBreakdown.push({
            size: uCol.size,
            ratio: ratio,
            units: units > 0 ? units : (plies * ratio)
          });
        }
      }

      if (markerObj.sizeBreakdown.length > 0) {
        ticket.markers.push(markerObj);
      }
    }
  }

  // Si no se capturó totalUnits de la etiqueta, sumamos las unidades de los marcadores
  let sumUnits = 0;
  const sizeMap = new Map();

  ticket.markers.forEach(m => {
    m.sizeBreakdown.forEach(s => {
      sumUnits += s.units;
      sizeMap.set(s.size, (sizeMap.get(s.size) || 0) + s.units);
    });
  });

  if (ticket.totalUnits === 0 && sumUnits > 0) {
    ticket.totalUnits = sumUnits;
  }

  ticket.sizesSummary = Array.from(sizeMap.entries()).map(([size, units]) => ({ size, units }));
  ticket.specialInstructions = ticket.specialInstructions.join('\n');

  return ticket;
}

module.exports = {
  parseCutTicket
};
