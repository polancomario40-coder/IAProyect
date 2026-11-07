const XLSX = require('xlsx');
const path = require('path');

const mtoPath = "C:\\Users\\Mario Polanco\\OneDrive - Soluciones Administrativas para Empresas (1)\\SWS\\CUTS\\CUT MTO MEXICO";

const files = [
  "MTO-13111_199PF-SPUN-PW_ARAMARK.xlsx",
  "MTO-13114_2553E-SN-NP_CINTAS.xlsx",
  "MTO-13124_82497-B RED SPUN PW_CINTAS.xlsx",
  "MTO-13129_82517-NB SPUN POP_CINTAS.xlsx"
];

for (const fileName of files) {
  const filePath = path.join(mtoPath, fileName);
  console.log('\n' + '='.repeat(80));
  console.log(`FILE: ${fileName}`);
  console.log('='.repeat(80));
  
  try {
    const wb = XLSX.readFile(filePath);
    console.log(`Sheets: ${wb.SheetNames.join(', ')}`);
    
    // Check all sheets for Order-related info
    for (const sheetName of wb.SheetNames) {
      const ws = wb.Sheets[sheetName];
      const data = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
      
      let foundOrder = false;
      
      // Search all cells for order/PO/ORD keywords
      for (let r = 0; r < data.length; r++) {
        for (let c = 0; c < data[r].length; c++) {
          const val = String(data[r][c] || '');
          if (/order|ORD\d|P\.O\.|PO\s*#|PO\s*No|Purchase|ORDN|order\s*no|order\s*num/i.test(val) ||
              /^\d{8,}$/.test(val.trim())) {  // Long numbers that could be order numbers
            if (!foundOrder) {
              console.log(`\n  Sheet: "${sheetName}" - Order-related cells:`);
              foundOrder = true;
            }
            const colLetter = String.fromCharCode(65 + c);
            const prevVal = c > 0 ? String(data[r][c-1] || '').substring(0, 20) : '';
            const nextVal = data[r][c+1] !== undefined ? String(data[r][c+1]).substring(0, 30) : '';
            console.log(`    Row ${r+1}, Col ${colLetter}: "${val.substring(0, 50)}"  prev:"${prevVal}"  next:"${nextVal}"`);
          }
        }
      }
      
      // For DATA sheet: print ALL non-empty content
      if (sheetName.toLowerCase().includes('data')) {
        console.log(`\n  Sheet: "${sheetName}" - ALL CONTENT:`);
        for (let r = 0; r < Math.min(data.length, 50); r++) {
          const row = data[r];
          if (!row || row.every(c => c === '' || c === null || c === undefined)) continue;
          const rowStr = row.map((cell, idx) => {
            const colLetter = idx < 26 ? String.fromCharCode(65 + idx) : `A${String.fromCharCode(65 + idx - 26)}`;
            if (cell !== '' && cell !== null && cell !== undefined) {
              return `[${colLetter}]"${String(cell).substring(0, 30)}"`;
            }
            return null;
          }).filter(Boolean).join('  ');
          if (rowStr) console.log(`    Row ${r+1}: ${rowStr}`);
        }
      }
    }
    
    // Now look for the Style field specifically in cut ticket sheet
    const ws = wb.Sheets[wb.SheetNames[0]];
    const data = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
    console.log('\n  --- Style extraction check ---');
    for (let r = 0; r < Math.min(data.length, 30); r++) {
      const row = data[r];
      for (let c = 0; c < row.length; c++) {
        const val = String(row[c] || '').trim();
        if (val === 'Style' || val === '(Estilo)' || val === 'style') {
          const nextVals = [];
          for (let cc = c+1; cc < Math.min(row.length, c+5); cc++) {
            if (row[cc] !== '') nextVals.push(`[${String.fromCharCode(65+cc)}]"${String(row[cc]).substring(0,20)}"`);
          }
          console.log(`  Row ${r+1}, Col ${String.fromCharCode(65+c)}: "Style" label, next cells: ${nextVals.join('  ')}`);
          // Also check the row BELOW for style value
          if (data[r+1]) {
            const belowVals = [];
            for (let cc = c; cc < Math.min(data[r+1].length, c+5); cc++) {
              if (data[r+1][cc] !== '') belowVals.push(`[${String.fromCharCode(65+cc)}]"${String(data[r+1][cc]).substring(0,20)}"`);
            }
            if (belowVals.length) console.log(`  Row ${r+2} (below): ${belowVals.join('  ')}`);
          }
        }
      }
    }
    
  } catch (e) {
    console.log(`ERROR: ${e.message}`);
  }
}
