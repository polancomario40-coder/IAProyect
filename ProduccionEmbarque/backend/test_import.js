const path = require('path');
const fs = require('fs');
const cutTicketService = require('./src/services/cutTicketService');
const { getPool, sql } = require('./src/config/db');

async function runTest() {
  try {
    const targetDir = path.resolve(__dirname, '..');
    const files = fs.readdirSync(targetDir).filter(f => f.startsWith('MTO-') && f.endsWith('.xlsx'));
    console.log(`Archivos encontrados en ${targetDir}:`, files);

    for (const f of files) {
      const fullPath = path.join(targetDir, f);
      console.log(`\n==================================================`);
      console.log(`Importando: ${f}`);
      console.log(`==================================================`);
      const res = await cutTicketService.importCutTicket(fullPath, f);
      console.log('Resultado:', res);
    }

    // Consultar el estado final de las tablas en SQL Server
    const pool = await getPool();
    console.log('\n--- CutTickets en DB ---');
    const tickets = await pool.request().query('SELECT IdCutTicket, CutNumber, Style, Customer, TotalUnits, Status FROM CutTickets');
    console.table(tickets.recordset);

    console.log('\n--- Conteo de Marcadores y Detalles ---');
    const markers = await pool.request().query('SELECT COUNT(*) AS total_markers FROM CutTicketMarkers');
    const details = await pool.request().query('SELECT COUNT(*) AS total_details FROM CutTicketDetails');
    const history = await pool.request().query('SELECT COUNT(*) AS total_history FROM CutTicketStatusHistory');
    console.log({
      total_markers: markers.recordset[0].total_markers,
      total_details: details.recordset[0].total_details,
      total_history: history.recordset[0].total_history
    });

    console.log('\n¡PRUEBA COMPLETADA CON ÉXITO!');
    process.exit(0);
  } catch (err) {
    console.error('Error durante la prueba:', err);
    process.exit(1);
  }
}

runTest();
