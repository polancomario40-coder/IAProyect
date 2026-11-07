const { sql, getPool } = require('../config/db');
const { parseCutTicket } = require('./cutTicketParser');

/**
 * Guarda o actualiza un Cut Ticket en SQL Server dentro de una transacción.
 */
async function importCutTicket(fileSource, fileName = 'CutTicket.xlsx') {
  const parsedData = parseCutTicket(fileSource);

  if (!parsedData.cutNumber) {
    throw new Error('No se pudo identificar el número de corte (MTO) en el archivo Excel.');
  }

  const pool = await getPool();
  const transaction = new sql.Transaction(pool);

  try {
    await transaction.begin();

    // 1. Verificar si ya existe el corte
    const checkReq = new sql.Request(transaction);
    checkReq.input('CutNumber', sql.VarChar(50), parsedData.cutNumber);
    const existing = await checkReq.query(`
      SELECT IdCutTicket, Status FROM CutTickets WHERE CutNumber = @CutNumber
    `);

    let cutTicketId;
    const isNew = existing.recordset.length === 0;

    if (isNew) {
      // INSERT en CutTickets
      const insertReq = new sql.Request(transaction);
      insertReq.input('CutNumber', sql.VarChar(50), parsedData.cutNumber);
      insertReq.input('OrderNumber', sql.VarChar(100), parsedData.orderNumber || null);
      insertReq.input('Style', sql.VarChar(100), parsedData.style || 'SIN ESTILO');
      insertReq.input('Customer', sql.VarChar(100), parsedData.customer || null);
      insertReq.input('GerberModel', sql.VarChar(100), parsedData.gerberModel || null);
      insertReq.input('Folder', sql.VarChar(100), parsedData.folder || null);
      insertReq.input('Fabric', sql.VarChar(150), parsedData.fabric || null);
      insertReq.input('FabricDesc', sql.VarChar(255), parsedData.fabricDesc || null);
      insertReq.input('Mill', sql.VarChar(100), parsedData.mill || null);
      insertReq.input('CuttableWidth', sql.VarChar(50), parsedData.cuttableWidth || null);
      insertReq.input('TotalUnits', sql.Int, parsedData.totalUnits || 0);
      insertReq.input('OrderDate', sql.DateTime, parsedData.orderDate || null);
      insertReq.input('CutDate', sql.DateTime, parsedData.cutDate || null);
      insertReq.input('RequireShipDate', sql.DateTime, parsedData.requireShipDate || null);
      insertReq.input('SpecialInstructions', sql.NVarChar(sql.MAX), parsedData.specialInstructions || null);
      insertReq.input('SourceFileName', sql.VarChar(255), fileName);

      const resInsert = await insertReq.query(`
        INSERT INTO CutTickets (
          CutNumber, OrderNumber, Style, Customer, GerberModel, Folder, Fabric, FabricDesc,
          Mill, CuttableWidth, TotalUnits, OrderDate, CutDate, RequireShipDate,
          SpecialInstructions, SourceFileName, Status
        )
        OUTPUT INSERTED.IdCutTicket
        VALUES (
          @CutNumber, @OrderNumber, @Style, @Customer, @GerberModel, @Folder, @Fabric, @FabricDesc,
          @Mill, @CuttableWidth, @TotalUnits, @OrderDate, @CutDate, @RequireShipDate,
          @SpecialInstructions, @SourceFileName, 'PENDIENTE_CORTE'
        );
      `);

      cutTicketId = resInsert.recordset[0].IdCutTicket;

      // Log inicial en historial WIP
      const histReq = new sql.Request(transaction);
      histReq.input('IdCutTicket', sql.Int, cutTicketId);
      histReq.input('NewStatus', sql.VarChar(50), 'PENDIENTE_CORTE');
      histReq.input('Notes', sql.NVarChar(500), `Importado desde Excel: ${fileName}`);
      await histReq.query(`
        INSERT INTO CutTicketStatusHistory (IdCutTicket, PreviousStatus, NewStatus, Notes)
        VALUES (@IdCutTicket, NULL, @NewStatus, @Notes);
      `);
    } else {
      cutTicketId = existing.recordset[0].IdCutTicket;

      // UPDATE de cabecera
      const updateReq = new sql.Request(transaction);
      updateReq.input('IdCutTicket', sql.Int, cutTicketId);
      updateReq.input('OrderNumber', sql.VarChar(100), parsedData.orderNumber || null);
      updateReq.input('Style', sql.VarChar(100), parsedData.style);
      updateReq.input('Customer', sql.VarChar(100), parsedData.customer);
      updateReq.input('GerberModel', sql.VarChar(100), parsedData.gerberModel);
      updateReq.input('Folder', sql.VarChar(100), parsedData.folder);
      updateReq.input('Fabric', sql.VarChar(150), parsedData.fabric);
      updateReq.input('FabricDesc', sql.VarChar(255), parsedData.fabricDesc);
      updateReq.input('Mill', sql.VarChar(100), parsedData.mill);
      updateReq.input('CuttableWidth', sql.VarChar(50), parsedData.cuttableWidth);
      updateReq.input('TotalUnits', sql.Int, parsedData.totalUnits);
      updateReq.input('SourceFileName', sql.VarChar(255), fileName);

      await updateReq.query(`
        UPDATE CutTickets
        SET OrderNumber = COALESCE(@OrderNumber, OrderNumber),
            Style = @Style, Customer = @Customer, GerberModel = @GerberModel,
            Folder = @Folder, Fabric = @Fabric, FabricDesc = @FabricDesc,
            Mill = @Mill, CuttableWidth = @CuttableWidth, TotalUnits = @TotalUnits,
            SourceFileName = @SourceFileName, UpdatedAt = GETDATE()
        WHERE IdCutTicket = @IdCutTicket;
      `);

      // Limpiar marcadores y detalles anteriores para recargarlos limpiamente
      const delReq = new sql.Request(transaction);
      delReq.input('IdCutTicket', sql.Int, cutTicketId);
      await delReq.query(`
        DELETE FROM CutTicketDetails WHERE IdCutTicket = @IdCutTicket;
        DELETE FROM CutTicketMarkers WHERE IdCutTicket = @IdCutTicket;
      `);
    }

    // 2. Insertar Marcadores y Detalles por Talla
    for (const marker of parsedData.markers) {
      const markerReq = new sql.Request(transaction);
      markerReq.input('IdCutTicket', sql.Int, cutTicketId);
      markerReq.input('MarkerName', sql.VarChar(100), marker.markerName);
      markerReq.input('FabricWidth', sql.VarChar(50), marker.fabricWidth);
      markerReq.input('MarkerLength', sql.Decimal(10, 2), marker.markerLength);
      markerReq.input('Efficiency', sql.Decimal(6, 2), marker.efficiency);
      markerReq.input('Plies', sql.Int, marker.plies);

      const markerRes = await markerReq.query(`
        INSERT INTO CutTicketMarkers (IdCutTicket, MarkerName, FabricWidth, MarkerLength, Efficiency, Plies)
        OUTPUT INSERTED.IdMarker
        VALUES (@IdCutTicket, @MarkerName, @FabricWidth, @MarkerLength, @Efficiency, @Plies);
      `);

      const markerId = markerRes.recordset[0].IdMarker;

      for (const sizeItem of marker.sizeBreakdown) {
        const detailReq = new sql.Request(transaction);
        detailReq.input('IdCutTicket', sql.Int, cutTicketId);
        detailReq.input('IdMarker', sql.Int, markerId);
        detailReq.input('Size', sql.VarChar(20), sizeItem.size);
        detailReq.input('Ratio', sql.Int, sizeItem.ratio);
        detailReq.input('Units', sql.Int, sizeItem.units);

        await detailReq.query(`
          INSERT INTO CutTicketDetails (IdCutTicket, IdMarker, Size, Ratio, Units)
          VALUES (@IdCutTicket, @IdMarker, @Size, @Ratio, @Units);
        `);
      }
    }

    await transaction.commit();

    return {
      success: true,
      action: isNew ? 'CREATED' : 'UPDATED',
      idCutTicket: cutTicketId,
      cutNumber: parsedData.cutNumber,
      orderNumber: parsedData.orderNumber,
      style: parsedData.style,
      customer: parsedData.customer,
      totalUnits: parsedData.totalUnits,
      markersCount: parsedData.markers.length,
      sizesSummary: parsedData.sizesSummary
    };
  } catch (err) {
    await transaction.rollback();
    throw err;
  }
}

/**
 * Consulta lista de Cut Tickets para visualización rápida.
 */
async function getAllCutTickets() {
  const pool = await getPool();
  const res = await pool.request().query(`
    SELECT 
      IdCutTicket, CutNumber, OrderNumber, Style, Customer, TotalUnits,
      Status, SourceFileName, CreatedAt, UpdatedAt
    FROM CutTickets
    ORDER BY IdCutTicket DESC
  `);
  return res.recordset;
}

/**
 * Consulta el detalle completo de un Cut Ticket por ID.
 */
async function getCutTicketById(id) {
  const pool = await getPool();

  const ticketReq = new sql.Request();
  ticketReq.input('Id', sql.Int, id);

  const ticketRes = await ticketReq.query(`
    SELECT * FROM CutTickets WHERE IdCutTicket = @Id;
  `);

  if (ticketRes.recordset.length === 0) return null;

  const ticket = ticketRes.recordset[0];

  const markersRes = await pool.request()
    .input('IdCutTicket', sql.Int, id)
    .query(`SELECT * FROM CutTicketMarkers WHERE IdCutTicket = @IdCutTicket`);

  const detailsRes = await pool.request()
    .input('IdCutTicket', sql.Int, id)
    .query(`SELECT * FROM CutTicketDetails WHERE IdCutTicket = @IdCutTicket`);

  const historyRes = await pool.request()
    .input('IdCutTicket', sql.Int, id)
    .query(`SELECT * FROM CutTicketStatusHistory WHERE IdCutTicket = @IdCutTicket ORDER BY ChangedAt DESC`);

  return {
    ...ticket,
    markers: markersRes.recordset,
    sizes: detailsRes.recordset,
    history: historyRes.recordset
  };
}

/**
 * Actualiza el estatus de un Cut Ticket y registra el cambio en el historial WIP.
 */
async function updateCutTicketStatus(id, newStatus, changedBy = 'SUPERVISOR', notes = null) {
  const validStatuses = ['PENDIENTE_CORTE', 'CORTADO', 'COSIENDO', 'INSPECCION', 'COMPLETADO', 'EMBARCADO'];
  if (!validStatuses.includes(newStatus)) {
    throw new Error(`Estatus inválido: '${newStatus}'. Valores permitidos: ${validStatuses.join(', ')}`);
  }

  const pool = await getPool();
  const transaction = new sql.Transaction(pool);

  try {
    await transaction.begin();

    // Obtener estatus actual
    const checkReq = new sql.Request(transaction);
    checkReq.input('Id', sql.Int, id);
    const existing = await checkReq.query(`SELECT Status FROM CutTickets WHERE IdCutTicket = @Id`);

    if (existing.recordset.length === 0) {
      throw new Error(`Cut Ticket con ID ${id} no fue encontrado.`);
    }

    const previousStatus = existing.recordset[0].Status;

    // Actualizar estatus
    const updateReq = new sql.Request(transaction);
    updateReq.input('Id', sql.Int, id);
    updateReq.input('Status', sql.VarChar(50), newStatus);
    await updateReq.query(`
      UPDATE CutTickets
      SET Status = @Status, UpdatedAt = GETDATE()
      WHERE IdCutTicket = @Id;
    `);

    // Insertar en historial WIP
    const histReq = new sql.Request(transaction);
    histReq.input('IdCutTicket', sql.Int, id);
    histReq.input('PreviousStatus', sql.VarChar(50), previousStatus);
    histReq.input('NewStatus', sql.VarChar(50), newStatus);
    histReq.input('ChangedBy', sql.VarChar(100), changedBy);
    histReq.input('Notes', sql.NVarChar(500), notes || `Cambio de estatus: ${previousStatus} -> ${newStatus}`);
    await histReq.query(`
      INSERT INTO CutTicketStatusHistory (IdCutTicket, PreviousStatus, NewStatus, ChangedBy, Notes)
      VALUES (@IdCutTicket, @PreviousStatus, @NewStatus, @ChangedBy, @Notes);
    `);

    await transaction.commit();

    return {
      success: true,
      idCutTicket: id,
      previousStatus,
      newStatus,
      changedAt: new Date()
    };
  } catch (err) {
    await transaction.rollback();
    throw err;
  }
}

/**
 * Resumen de métricas WIP para el panel de control.
 */
async function getWipSummary() {
  const pool = await getPool();

  const resStatus = await pool.request().query(`
    SELECT 
      Status,
      COUNT(*) AS TotalOrders,
      ISNULL(SUM(TotalUnits), 0) AS TotalUnits
    FROM CutTickets
    GROUP BY Status;
  `);

  const resTotals = await pool.request().query(`
    SELECT 
      COUNT(*) AS TotalOrders,
      ISNULL(SUM(TotalUnits), 0) AS TotalUnits
    FROM CutTickets;
  `);

  return {
    overall: resTotals.recordset[0],
    byStatus: resStatus.recordset
  };
}

module.exports = {
  importCutTicket,
  getAllCutTickets,
  getCutTicketById,
  updateCutTicketStatus,
  getWipSummary
};

