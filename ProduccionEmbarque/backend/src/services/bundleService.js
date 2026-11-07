const { sql, getPool } = require('../config/db');

/**
 * Genera las etiquetas de paquetes (bundles) para un Cut Ticket dado.
 * @param {number} idCutTicket - ID de la orden de corte
 * @param {number|null} bundleSize - Tamaño máximo de prendas por bulto (si es null o 0, se crea un bulto por desglose de talla)
 */
async function generateBundles(idCutTicket, bundleSize = null) {
  const pool = await getPool();
  const transaction = new sql.Transaction(pool);

  try {
    await transaction.begin();

    // 1. Obtener la información del Cut Ticket
    const ticketReq = new sql.Request(transaction);
    ticketReq.input('Id', sql.Int, idCutTicket);
    const ticketRes = await ticketReq.query(`
      SELECT IdCutTicket, CutNumber, Style, Customer, TotalUnits, Status 
      FROM CutTickets 
      WHERE IdCutTicket = @Id;
    `);

    if (ticketRes.recordset.length === 0) {
      throw new Error(`Cut Ticket #${idCutTicket} no encontrado.`);
    }

    const ticket = ticketRes.recordset[0];

    // 2. Obtener los detalles de tallas y cantidades
    const detailsReq = new sql.Request(transaction);
    detailsReq.input('IdCutTicket', sql.Int, idCutTicket);
    const detailsRes = await detailsReq.query(`
      SELECT Size, SUM(Units) AS Units
      FROM CutTicketDetails
      WHERE IdCutTicket = @IdCutTicket
      GROUP BY Size
      ORDER BY Size;
    `);

    if (detailsRes.recordset.length === 0) {
      throw new Error(`El Cut Ticket #${idCutTicket} no tiene desglose de tallas registrado.`);
    }

    // 3. Eliminar etiquetas previas del mismo ticket para regenerar limpiamente
    const delReq = new sql.Request(transaction);
    delReq.input('IdCutTicket', sql.Int, idCutTicket);
    await delReq.query(`DELETE FROM CutTicketBundles WHERE IdCutTicket = @IdCutTicket;`);

    // 4. Calcular y generar bultos por cada talla
    let bundleSequence = 1;
    const generatedBundles = [];
    const maxPerBundle = parseInt(bundleSize, 10) > 0 ? parseInt(bundleSize, 10) : null;

    for (const item of detailsRes.recordset) {
      const size = item.Size;
      const totalUnitsForSize = item.Units;

      if (totalUnitsForSize <= 0) continue;

      if (!maxPerBundle || totalUnitsForSize <= maxPerBundle) {
        // Un solo bulto para esta talla
        generatedBundles.push({
          bundleNumber: bundleSequence++,
          size: size,
          quantity: totalUnitsForSize
        });
      } else {
        // Dividir en múltiples bultos del tamaño indicado
        let remaining = totalUnitsForSize;
        while (remaining > 0) {
          const qty = remaining >= maxPerBundle ? maxPerBundle : remaining;
          generatedBundles.push({
            bundleNumber: bundleSequence++,
            size: size,
            quantity: qty
          });
          remaining -= qty;
        }
      }
    }

    // 5. Insertar cada bulto en CutTicketBundles con su código de barra único
    const totalBundlesCount = generatedBundles.length;
    const cleanCutNumber = ticket.CutNumber.replace(/[^a-zA-Z0-9]/g, '');

    for (const b of generatedBundles) {
      // Barcode formato: PKG-{IdCutTicket}-{Seq3Digits} ej: PKG-1-001
      const barcode = `PKG-${ticket.IdCutTicket}-${String(b.bundleNumber).padStart(3, '0')}`;

      const insertReq = new sql.Request(transaction);
      insertReq.input('IdCutTicket', sql.Int, idCutTicket);
      insertReq.input('Barcode', sql.VarChar(50), barcode);
      insertReq.input('BundleNumber', sql.Int, b.bundleNumber);
      insertReq.input('Size', sql.VarChar(20), b.size);
      insertReq.input('Quantity', sql.Int, b.quantity);

      await insertReq.query(`
        INSERT INTO CutTicketBundles (IdCutTicket, Barcode, BundleNumber, Size, Quantity, Status)
        VALUES (@IdCutTicket, @Barcode, @BundleNumber, @Size, @Quantity, 'PENDIENTE');
      `);

      b.barcode = barcode;
      b.totalBundles = totalBundlesCount;
      b.cutNumber = ticket.CutNumber;
      b.style = ticket.Style;
      b.customer = ticket.Customer;
    }

    await transaction.commit();

    return {
      success: true,
      idCutTicket: ticket.IdCutTicket,
      cutNumber: ticket.CutNumber,
      style: ticket.Style,
      customer: ticket.Customer,
      totalBundles: generatedBundles.length,
      bundles: generatedBundles
    };
  } catch (err) {
    await transaction.rollback();
    throw err;
  }
}

/**
 * Consulta las etiquetas de paquetes de un Cut Ticket.
 */
async function getBundlesByCutTicket(idCutTicket) {
  const pool = await getPool();

  const ticketReq = new sql.Request();
  ticketReq.input('Id', sql.Int, idCutTicket);
  const ticketRes = await ticketReq.query(`
    SELECT IdCutTicket, CutNumber, Style, Customer, TotalUnits, Status 
    FROM CutTickets 
    WHERE IdCutTicket = @Id;
  `);

  if (ticketRes.recordset.length === 0) return null;
  const ticket = ticketRes.recordset[0];

  const bundlesReq = new sql.Request();
  bundlesReq.input('IdCutTicket', sql.Int, idCutTicket);
  const bundlesRes = await bundlesReq.query(`
    SELECT IdBundle, IdCutTicket, Barcode, BundleNumber, Size, Quantity, Status, ScannedAt, CreatedAt
    FROM CutTicketBundles
    WHERE IdCutTicket = @IdCutTicket
    ORDER BY BundleNumber ASC;
  `);

  const totalBundles = bundlesRes.recordset.length;
  const formattedBundles = bundlesRes.recordset.map(b => ({
    ...b,
    totalBundles,
    cutNumber: ticket.CutNumber,
    style: ticket.Style,
    customer: ticket.Customer
  }));

  return {
    ticket,
    totalBundles,
    bundles: formattedBundles
  };
}

/**
 * Elimina las etiquetas de un ticket para permitir regeneración.
 */
async function deleteBundles(idCutTicket) {
  const pool = await getPool();
  const req = new sql.Request();
  req.input('IdCutTicket', sql.Int, idCutTicket);
  const res = await req.query(`
    DELETE FROM CutTicketBundles 
    WHERE IdCutTicket = @IdCutTicket AND Status = 'PENDIENTE';
  `);
  return { deleted: res.rowsAffected[0] };
}

module.exports = {
  generateBundles,
  getBundlesByCutTicket,
  deleteBundles
};
