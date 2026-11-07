const { sql, getPool } = require('../config/db');

/**
 * Crea o recupera un Packing List / Contenedor.
 */
async function createOrGetPackingList(containerNumber, customer = null, shipDate = null, notes = null) {
  if (!containerNumber || !containerNumber.trim()) {
    throw new Error('El número de contenedor es requerido.');
  }

  const cleanContainer = containerNumber.trim().toUpperCase();
  const pool = await getPool();

  const checkReq = new sql.Request();
  checkReq.input('Container', sql.VarChar(50), cleanContainer);
  const existing = await checkReq.query(`
    SELECT * FROM PackingLists WHERE ContainerNumber = @Container;
  `);

  if (existing.recordset.length > 0) {
    return existing.recordset[0];
  }

  const insertReq = new sql.Request();
  insertReq.input('Container', sql.VarChar(50), cleanContainer);
  insertReq.input('Customer', sql.VarChar(100), customer);
  insertReq.input('ShipDate', sql.DateTime, shipDate ? new Date(shipDate) : new Date());
  insertReq.input('Notes', sql.NVarChar(500), notes);

  const res = await insertReq.query(`
    INSERT INTO PackingLists (ContainerNumber, Customer, ShipDate, Notes, Status)
    OUTPUT INSERTED.*
    VALUES (@Container, @Customer, @ShipDate, @Notes, 'ABIERTO');
  `);

  return res.recordset[0];
}

/**
 * Lista los contenedores de embarque registrados.
 */
async function getPackingLists() {
  const pool = await getPool();
  const res = await pool.request().query(`
    SELECT 
      p.IdPackingList,
      p.ContainerNumber,
      p.Customer,
      p.ShipDate,
      p.Status,
      p.Notes,
      p.CreatedAt,
      COUNT(b.IdBundle) AS TotalScannedBundles,
      ISNULL(SUM(b.Quantity), 0) AS TotalUnits,
      COUNT(DISTINCT b.BoxNumber) AS TotalBoxes
    FROM PackingLists p
    LEFT JOIN CutTicketBundles b ON p.IdPackingList = b.IdPackingList
    GROUP BY p.IdPackingList, p.ContainerNumber, p.Customer, p.ShipDate, p.Status, p.Notes, p.CreatedAt
    ORDER BY p.IdPackingList DESC;
  `);
  return res.recordset;
}

/**
 * Procesa la lectura de un código de barras de bulto para el empaque.
 * Realiza validaciones atómicas para evitar duplicados o inconsistencias.
 */
async function scanBundle(barcode, idPackingList, boxNumber = 1) {
  if (!barcode || !barcode.trim()) {
    throw new Error('Código de barra vacío.');
  }

  const cleanBarcode = barcode.trim().toUpperCase();
  const targetBox = parseInt(boxNumber, 10) || 1;
  const pool = await getPool();
  const transaction = new sql.Transaction(pool);

  try {
    await transaction.begin();

    // 1. Verificar el contenedor
    const pkgReq = new sql.Request(transaction);
    pkgReq.input('IdPkg', sql.Int, idPackingList);
    const pkgRes = await pkgReq.query(`SELECT * FROM PackingLists WHERE IdPackingList = @IdPkg`);
    if (pkgRes.recordset.length === 0) {
      throw new Error(`El contenedor de embarque #${idPackingList} no existe.`);
    }

    const packingList = pkgRes.recordset[0];
    if (packingList.Status === 'DESPACHADO') {
      throw new Error(`El contenedor ${packingList.ContainerNumber} ya fue despachado y está cerrado.`);
    }

    // 2. Buscar el paquete por código de barras interno o código de orden de cliente (CINTAS)
    const bundleReq = new sql.Request(transaction);
    bundleReq.input('Barcode', sql.VarChar(50), cleanBarcode);
    const bundleRes = await bundleReq.query(`
      SELECT b.*, t.CutNumber, t.OrderNumber, t.Style, t.Customer
      FROM CutTicketBundles b
      INNER JOIN CutTickets t ON b.IdCutTicket = t.IdCutTicket
      WHERE b.Barcode = @Barcode 
         OR b.CustomerBarcode = @Barcode
         OR (t.OrderNumber = @Barcode AND b.Status != 'EMPACADO');
    `);

    if (bundleRes.recordset.length === 0) {
      throw new Error(`La etiqueta con código [${cleanBarcode}] no existe en la base de datos.`);
    }

    const bundle = bundleRes.recordset[0];

    // 3. Validar si ya fue escaneada
    if (bundle.Status === 'EMPACADO' || bundle.IdPackingList !== null) {
      const alreadyIn = bundle.IdPackingList === idPackingList ? 'este mismo contenedor' : 'otro contenedor';
      throw new Error(`ALERTA: La etiqueta [${cleanBarcode}] ya fue leída previamente en ${alreadyIn} (Caja #${bundle.BoxNumber || 1}).`);
    }

    // 4. Actualizar el paquete como EMPACADO y asignarlo al contenedor y caja
    const updateBundleReq = new sql.Request(transaction);
    updateBundleReq.input('IdBundle', sql.Int, bundle.IdBundle);
    updateBundleReq.input('IdPackingList', sql.Int, idPackingList);
    updateBundleReq.input('BoxNumber', sql.Int, targetBox);
    await updateBundleReq.query(`
      UPDATE CutTicketBundles
      SET IdPackingList = @IdPackingList,
          BoxNumber = @BoxNumber,
          Status = 'EMPACADO',
          ScannedAt = GETDATE()
      WHERE IdBundle = @IdBundle;
    `);

    // 5. Verificar si todos los paquetes de este Cut Ticket ya fueron escaneados
    const checkAllReq = new sql.Request(transaction);
    checkAllReq.input('IdCutTicket', sql.Int, bundle.IdCutTicket);
    const checkAllRes = await checkAllReq.query(`
      SELECT 
        COUNT(*) AS TotalBundles,
        SUM(CASE WHEN Status = 'EMPACADO' THEN 1 ELSE 0 END) AS PackedBundles
      FROM CutTicketBundles
      WHERE IdCutTicket = @IdCutTicket;
    `);

    const { TotalBundles, PackedBundles } = checkAllRes.recordset[0];
    let ticketStatusUpdated = false;

    // Si todos los bultos del ticket están empacados, promover el ticket a INSPECCION/EMPAQUE o COMPLETADO
    if (TotalBundles > 0 && TotalBundles === PackedBundles) {
      const updateTicketReq = new sql.Request(transaction);
      updateTicketReq.input('IdCutTicket', sql.Int, bundle.IdCutTicket);
      await updateTicketReq.query(`
        UPDATE CutTickets
        SET Status = 'COMPLETADO', UpdatedAt = GETDATE()
        WHERE IdCutTicket = @IdCutTicket;

        INSERT INTO CutTicketStatusHistory (IdCutTicket, PreviousStatus, NewStatus, ChangedBy, Notes)
        VALUES (@IdCutTicket, 'INSPECCION', 'COMPLETADO', 'SCANNER_EMPAQUE', 'Todos los bultos han sido escaneados y empacados en contenedor');
      `);
      ticketStatusUpdated = true;
    }

    await transaction.commit();

    return {
      success: true,
      barcode: cleanBarcode,
      cutNumber: bundle.CutNumber,
      style: bundle.Style,
      size: bundle.Size,
      quantity: bundle.Quantity,
      bundleNumber: bundle.BundleNumber,
      boxNumber: targetBox,
      containerNumber: packingList.ContainerNumber,
      ticketCompleted: ticketStatusUpdated,
      scannedAt: new Date()
    };
  } catch (err) {
    await transaction.rollback();
    throw err;
  }
}

/**
 * Reporte agrupado de Packing List para exportación o impresión.
 */
async function getPackingReport(idPackingList) {
  const pool = await getPool();

  const pkgReq = new sql.Request();
  pkgReq.input('IdPkg', sql.Int, idPackingList);
  const pkgRes = await pkgReq.query(`SELECT * FROM PackingLists WHERE IdPackingList = @IdPkg`);

  if (pkgRes.recordset.length === 0) {
    throw new Error('Contenedor no encontrado.');
  }

  const packingList = pkgRes.recordset[0];

  // Agrupación por Cut #, Estilo, Caja y Talla
  const itemsReq = new sql.Request();
  itemsReq.input('IdPkg', sql.Int, idPackingList);
  const itemsRes = await itemsReq.query(`
    SELECT 
      t.CutNumber,
      t.Style,
      t.Customer,
      b.BoxNumber,
      b.Size,
      COUNT(b.IdBundle) AS BundleCount,
      SUM(b.Quantity) AS TotalUnits
    FROM CutTicketBundles b
    INNER JOIN CutTickets t ON b.IdCutTicket = t.IdCutTicket
    WHERE b.IdPackingList = @IdPkg
    GROUP BY t.CutNumber, t.Style, t.Customer, b.BoxNumber, b.Size
    ORDER BY b.BoxNumber ASC, t.CutNumber ASC, b.Size ASC;
  `);

  // Lista de bultos detallados individuales
  const bundlesReq = new sql.Request();
  bundlesReq.input('IdPkg', sql.Int, idPackingList);
  const bundlesRes = await bundlesReq.query(`
    SELECT 
      b.IdBundle,
      b.Barcode,
      b.BoxNumber,
      b.BundleNumber,
      b.Size,
      b.Quantity,
      b.ScannedAt,
      t.CutNumber,
      t.Style,
      t.Customer
    FROM CutTicketBundles b
    INNER JOIN CutTickets t ON b.IdCutTicket = t.IdCutTicket
    WHERE b.IdPackingList = @IdPkg
    ORDER BY b.ScannedAt DESC;
  `);

  let totalBoxes = 0;
  let totalUnits = 0;
  itemsRes.recordset.forEach(i => {
    totalUnits += i.TotalUnits;
  });

  const uniqueBoxes = new Set(itemsRes.recordset.map(i => i.BoxNumber));
  totalBoxes = uniqueBoxes.size;

  return {
    packingList,
    totalBoxes,
    totalUnits,
    summaryItems: itemsRes.recordset,
    scannedBundles: bundlesRes.recordset
  };
}

/**
 * Despacha / Cierra un contenedor oficialmente.
 */
async function dispatchPackingList(idPackingList) {
  const pool = await getPool();
  const transaction = new sql.Transaction(pool);

  try {
    await transaction.begin();

    // Actualizar contenedor
    const updatePkg = new sql.Request(transaction);
    updatePkg.input('IdPkg', sql.Int, idPackingList);
    await updatePkg.query(`
      UPDATE PackingLists 
      SET Status = 'DESPACHADO', UpdatedAt = GETDATE()
      WHERE IdPackingList = @IdPkg;
    `);

    // Actualizar tickets a EMBARCADO
    const updateTickets = new sql.Request(transaction);
    updateTickets.input('IdPkg', sql.Int, idPackingList);
    await updateTickets.query(`
      UPDATE CutTickets
      SET Status = 'EMBARCADO', UpdatedAt = GETDATE()
      WHERE IdCutTicket IN (
        SELECT DISTINCT IdCutTicket FROM CutTicketBundles WHERE IdPackingList = @IdPkg
      );

      INSERT INTO CutTicketStatusHistory (IdCutTicket, PreviousStatus, NewStatus, ChangedBy, Notes)
      SELECT DISTINCT 
        IdCutTicket, 
        'COMPLETADO', 
        'EMBARCADO', 
        'DESPACHO_EMBARQUE', 
        'Contenedor despachado'
      FROM CutTicketBundles
      WHERE IdPackingList = @IdPkg;
    `);

    await transaction.commit();
    return { success: true, message: 'Contenedor despachado exitosamente.' };
  } catch (err) {
    await transaction.rollback();
    throw err;
  }
}

/**
 * Quita un bulto escaneado del contenedor/caja para permitir escanearlo nuevamente.
 */
async function unscanBundle(idBundle) {
  const pool = await getPool();
  const transaction = new sql.Transaction(pool);

  try {
    await transaction.begin();

    // 1. Obtener datos del bulto
    const checkReq = new sql.Request(transaction);
    checkReq.input('IdBundle', sql.Int, idBundle);
    const bundleRes = await checkReq.query(`
      SELECT b.*, t.CutNumber, t.Status AS TicketStatus 
      FROM CutTicketBundles b
      INNER JOIN CutTickets t ON b.IdCutTicket = t.IdCutTicket
      WHERE b.IdBundle = @IdBundle;
    `);

    if (bundleRes.recordset.length === 0) {
      throw new Error(`El bulto con ID #${idBundle} no existe.`);
    }

    const bundle = bundleRes.recordset[0];

    // 2. Liberar el bulto
    const resetReq = new sql.Request(transaction);
    resetReq.input('IdBundle', sql.Int, idBundle);
    await resetReq.query(`
      UPDATE CutTicketBundles
      SET IdPackingList = NULL,
          BoxNumber = NULL,
          Status = 'PENDIENTE',
          ScannedAt = NULL
      WHERE IdBundle = @IdBundle;
    `);

    // 3. Si el Cut Ticket estaba marcado como COMPLETADO o EMBARCADO, regresarlo a INSPECCION
    if (bundle.TicketStatus === 'COMPLETADO' || bundle.TicketStatus === 'EMBARCADO') {
      const updateTicketReq = new sql.Request(transaction);
      updateTicketReq.input('IdCutTicket', sql.Int, bundle.IdCutTicket);
      await updateTicketReq.query(`
        UPDATE CutTickets
        SET Status = 'INSPECCION', UpdatedAt = GETDATE()
        WHERE IdCutTicket = @IdCutTicket;

        INSERT INTO CutTicketStatusHistory (IdCutTicket, PreviousStatus, NewStatus, ChangedBy, Notes)
        VALUES (@IdCutTicket, '${bundle.TicketStatus}', 'INSPECCION', 'SCANNER_EMPAQUE', 'Bulto [${bundle.Barcode}] quitado de la caja/contenedor.');
      `);
    }

    await transaction.commit();

    return {
      success: true,
      barcode: bundle.Barcode,
      cutNumber: bundle.CutNumber,
      message: `Bulto [${bundle.Barcode}] quitado del contenedor. Ahora puede ser escaneado nuevamente.`
    };
  } catch (err) {
    await transaction.rollback();
    throw err;
  }
}

module.exports = {
  createOrGetPackingList,
  getPackingLists,
  scanBundle,
  getPackingReport,
  dispatchPackingList,
  unscanBundle
};
