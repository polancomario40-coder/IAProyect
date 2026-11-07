const { getPool, sql } = require('./src/config/db');

async function checkAndMigrate() {
  try {
    const pool = await getPool();
    console.log('Conectado a SQL Server.');

    // 1. Columnas actuales de CutTickets
    const cols = await pool.request().query(`
      SELECT COLUMN_NAME, DATA_TYPE 
      FROM INFORMATION_SCHEMA.COLUMNS 
      WHERE TABLE_NAME = 'CutTickets'
    `);
    console.log('Columnas actuales en CutTickets:');
    console.log(cols.recordset.map(c => c.COLUMN_NAME).join(', '));

    // 2. Agregar OrderNumber si no existe
    const hasOrderNumber = cols.recordset.some(c => c.COLUMN_NAME.toLowerCase() === 'ordernumber');
    if (!hasOrderNumber) {
      console.log('Agregando columna OrderNumber a CutTickets...');
      await pool.request().query(`
        ALTER TABLE CutTickets ADD OrderNumber VARCHAR(100) NULL;
        CREATE INDEX IX_CutTickets_OrderNumber ON CutTickets(OrderNumber);
      `);
      console.log('Columna OrderNumber agregada exitosamente.');
    } else {
      console.log('La columna OrderNumber ya existe.');
    }

    // 3. Verificar CutTicketBundles por si acaso
    const bundleCols = await pool.request().query(`
      SELECT COLUMN_NAME 
      FROM INFORMATION_SCHEMA.COLUMNS 
      WHERE TABLE_NAME = 'CutTicketBundles'
    `);
    console.log('Columnas en CutTicketBundles:');
    console.log(bundleCols.recordset.map(c => c.COLUMN_NAME).join(', '));

    const hasCustomerBarcode = bundleCols.recordset.some(c => c.COLUMN_NAME.toLowerCase() === 'customerbarcode');
    if (!hasCustomerBarcode) {
      console.log('Agregando columna CustomerBarcode a CutTicketBundles...');
      await pool.request().query(`
        ALTER TABLE CutTicketBundles ADD CustomerBarcode VARCHAR(100) NULL;
        CREATE INDEX IX_CutTicketBundles_CustomerBarcode ON CutTicketBundles(CustomerBarcode);
      `);
      console.log('Columna CustomerBarcode agregada exitosamente.');
    } else {
      console.log('La columna CustomerBarcode ya existe.');
    }

    process.exit(0);
  } catch (err) {
    console.error('Error en migración:', err);
    process.exit(1);
  }
}

checkAndMigrate();
