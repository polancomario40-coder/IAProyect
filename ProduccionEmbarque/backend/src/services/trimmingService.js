const { sql, getPool } = require('../config/db');

/**
 * Servicio de Trimmings / Accesorios de Inventario (BOM Multinivel)
 * Integra explosión recursiva de materiales y salidas directas al ERP SADE (sws)
 */

/**
 * Busca productos / estilos en la tabla Producto del ERP SADE para asociación manual si se requiere.
 */
async function searchProducts(searchTerm, limit = 20) {
  const pool = await getPool();
  const term = `%${searchTerm || ''}%`;

  const res = await pool.request()
    .input('term', sql.VarChar(100), term)
    .input('limit', sql.Int, limit)
    .query(`
      SELECT TOP (@limit)
        p.idProducto,
        p.Producto,
        p.Referencia,
        p.Compuesto,
        p.idUnidad,
        ISNULL(p.UltimoCosto, 0) AS UltimoCosto,
        (SELECT COUNT(*) FROM ProductoDet pd WHERE pd.idProducto = p.idProducto) AS TotalComponentes
      FROM Producto p
      WHERE p.Inactivo = 0
        AND (p.idProducto LIKE @term OR p.Producto LIKE @term OR p.Referencia LIKE @term)
      ORDER BY p.Compuesto DESC, p.idProducto ASC;
    `);

  return res.recordset;
}

/**
 * Intenta resolver automáticamente el idProducto en ERP SADE que corresponde a la cadena de estilo de un Cut Ticket.
 * Ej: '82517-NB SPUN POP' -> busca '82517-NB SPUN POP', '08251700RG', '82517-COLOR', etc.
 */
async function matchStyleToProduct(styleString) {
  if (!styleString) return null;
  const pool = await getPool();
  const cleanStyle = styleString.trim();

  // 1. Coincidencia exacta por idProducto o Referencia o Producto
  let res = await pool.request()
    .input('style', sql.VarChar(100), cleanStyle)
    .query(`
      SELECT TOP 1 idProducto, Producto, Compuesto, idUnidad, ISNULL(UltimoCosto, 0) AS UltimoCosto
      FROM Producto
      WHERE idProducto = @style OR Referencia = @style OR Producto = @style
    `);

  if (res.recordset.length > 0) return res.recordset[0];

  // 2. Extraer el primer token de estilo (ej. '82517' o '199PF' o '2553E')
  const baseCodeMatch = cleanStyle.match(/^([0-9a-zA-Z]+(?:-[0-9a-zA-Z]+)?)/);
  if (baseCodeMatch) {
    const baseCode = baseCodeMatch[1];
    res = await pool.request()
      .input('baseCode', sql.VarChar(100), `%${baseCode}%`)
      .query(`
        SELECT TOP 1 idProducto, Producto, Compuesto, idUnidad, ISNULL(UltimoCosto, 0) AS UltimoCosto
        FROM Producto
        WHERE (idProducto LIKE @baseCode OR Referencia LIKE @baseCode OR Producto LIKE @baseCode)
          AND Compuesto = 1
        ORDER BY CASE WHEN idProducto LIKE @baseCode THEN 0 ELSE 1 END, idProducto ASC
      `);

    if (res.recordset.length > 0) return res.recordset[0];
  }

  // 3. Búsqueda por número si el estilo contiene dígitos principales (ej. 82517)
  const numbersOnly = cleanStyle.match(/\d{4,}/);
  if (numbersOnly) {
    res = await pool.request()
      .input('num', sql.VarChar(50), `%${numbersOnly[0]}%`)
      .query(`
        SELECT TOP 1 idProducto, Producto, Compuesto, idUnidad, ISNULL(UltimoCosto, 0) AS UltimoCosto
        FROM Producto
        WHERE (idProducto LIKE @num OR Producto LIKE @num)
          AND Compuesto = 1
        ORDER BY idProducto ASC
      `);

    if (res.recordset.length > 0) return res.recordset[0];
  }

  return null;
}

/**
 * Función recursiva que recorre el árbol de ProductoDet hasta llegar a los productos hojas físicas (accesorios/trimmings).
 */
async function explodeBOM(pool, parentId, parentQty = 1, level = 1, visited = new Set()) {
  if (visited.has(parentId)) {
    console.warn(`[Ciclo Detectado] Producto ${parentId} ya fue visitado en este árbol.`);
    return { treeNodes: [], leafItems: [] };
  }
  visited.add(parentId);

  const query = `
    SELECT 
      pd.idProductoDet,
      pd.Cantidad,
      pd.Producto AS DetalleNombre,
      ISNULL(p.Producto, pd.Producto) AS ProductoDesc,
      p.Compuesto,
      ISNULL(p.idUnidad, 'Unidad') AS idUnidad,
      ISNULL(p.UltimoCosto, ISNULL(pd.Costo, 0)) AS Costo
    FROM ProductoDet pd
    LEFT JOIN Producto p ON p.idProducto = pd.idProductoDet
    WHERE pd.idProducto = @idProducto
  `;

  const res = await pool.request()
    .input('idProducto', sql.VarChar(25), parentId)
    .query(query);

  const treeNodes = [];
  const leafItems = [];

  for (const item of res.recordset) {
    const isCompound = item.Compuesto === true || item.Compuesto === 1;
    const currentQty = parentQty * item.Cantidad;

    const node = {
      idProducto: item.idProductoDet,
      producto: item.ProductoDesc,
      cantidadUnitaria: item.Cantidad,
      cantidadAcumulada: currentQty,
      idUnidad: item.idUnidad,
      costo: item.Costo,
      esCompuesto: isCompound,
      nivel: level,
      padreId: parentId,
      subComponentes: []
    };

    if (isCompound) {
      // Intentar desglose recursivo
      const sub = await explodeBOM(pool, item.idProductoDet, currentQty, level + 1, new Set(visited));
      if (sub.leafItems.length > 0) {
        node.subComponentes = sub.treeNodes;
        leafItems.push(...sub.leafItems);
      } else {
        // Marcado como compuesto pero sin hijos definidos: se toma como hoja física
        leafItems.push({
          idProducto: item.idProductoDet,
          producto: item.ProductoDesc,
          cantidadUnitaria: item.Cantidad,
          cantidadTotal: currentQty,
          idUnidad: item.idUnidad,
          costo: item.Costo,
          padreId: parentId,
          nivel: level
        });
      }
    } else {
      leafItems.push({
        idProducto: item.idProductoDet,
        producto: item.ProductoDesc,
        cantidadUnitaria: item.Cantidad,
        cantidadTotal: currentQty,
        idUnidad: item.idUnidad,
        costo: item.Costo,
        padreId: parentId,
        nivel: level
      });
    }

    treeNodes.push(node);
  }

  return { treeNodes, leafItems };
}

/**
 * Genera la explosión completa de materiales para una orden de corte o combinación Estilo/Unidades.
 */
async function getExplosionData({ idCutTicket, style, totalUnits, customProductId }) {
  const pool = await getPool();

  let ticket = null;
  let targetStyle = style;
  let targetUnits = parseInt(totalUnits, 10) || 0;

  if (idCutTicket) {
    const ticketRes = await pool.request()
      .input('id', sql.Int, idCutTicket)
      .query(`SELECT * FROM CutTickets WHERE IdCutTicket = @id;`);

    if (ticketRes.recordset.length === 0) {
      throw new Error(`Cut Ticket #${idCutTicket} no fue encontrado.`);
    }

    ticket = ticketRes.recordset[0];
    targetStyle = ticket.Style;
    targetUnits = ticket.TotalUnits || targetUnits;
  }

  // Resolver producto ERP asociado
  let erpProduct = null;
  if (customProductId) {
    const pRes = await pool.request()
      .input('id', sql.VarChar(25), customProductId.trim())
      .query(`SELECT idProducto, Producto, Compuesto, idUnidad, ISNULL(UltimoCosto, 0) AS UltimoCosto FROM Producto WHERE idProducto = @id;`);
    if (pRes.recordset.length > 0) erpProduct = pRes.recordset[0];
  }

  if (!erpProduct && targetStyle) {
    erpProduct = await matchStyleToProduct(targetStyle);
  }

  if (!erpProduct) {
    return {
      success: false,
      hasBOM: false,
      message: `No se encontró una equivalencia directa para el estilo '${targetStyle}' en el catálogo ERP Producto. Por favor seleccione el producto ERP correspondiente.`,
      ticket,
      targetStyle,
      targetUnits,
      erpProduct: null,
      tree: [],
      consolidated: []
    };
  }

  // Realizar la explosión recursiva con la cantidad total de prendas del corte
  const { treeNodes, leafItems } = await explodeBOM(pool, erpProduct.idProducto, targetUnits);

  // Consolidar cantidades netas por idProducto
  const consolidatedMap = new Map();
  for (const leaf of leafItems) {
    const key = leaf.idProducto.trim();
    if (!consolidatedMap.has(key)) {
      consolidatedMap.set(key, {
        idProducto: key,
        producto: leaf.producto,
        cantidadUnitaria: leaf.cantidadUnitaria,
        cantidadTotal: 0,
        idUnidad: leaf.idUnidad,
        costo: leaf.costo
      });
    }
    const current = consolidatedMap.get(key);
    current.cantidadTotal = Math.round((current.cantidadTotal + leaf.cantidadTotal) * 1000) / 1000;
  }

  const consolidatedList = Array.from(consolidatedMap.values());

  // Verificar si ya existe movimiento ProMov registrado para este corte
  let existingProMov = null;
  if (ticket && ticket.CutNumber) {
    const movRes = await pool.request()
      .input('ref', sql.VarChar(20), ticket.CutNumber.trim())
      .input('idTipo', sql.Int, 11) // SAL PRODUCCION
      .query(`
        SELECT TOP 1 idProMov, idProMovTipo, ProMov, Fecha, Referencia, Concepto, idAlmacen, Usuario, Posteado
        FROM ProMov
        WHERE Referencia = @ref AND Salida = 1 AND idProMovTipo = @idTipo
        ORDER BY Fecha DESC;
      `);

    if (movRes.recordset.length > 0) {
      existingProMov = movRes.recordset[0];
    }
  }

  return {
    success: true,
    hasBOM: consolidatedList.length > 0,
    ticket,
    targetStyle,
    targetUnits,
    erpProduct,
    existingProMov,
    tree: treeNodes,
    consolidated: consolidatedList
  };
}

/**
 * Consulta la lista de órdenes de corte con su estado de materiales y filtros avanzados.
 */
async function getCutsTrimmingList(filters = {}) {
  const pool = await getPool();
  const { search, status, trimmingStatus, startDate, endDate, limit = 100 } = filters;

  let query = `
    SELECT 
      c.IdCutTicket,
      c.CutNumber,
      c.OrderNumber,
      c.Style,
      c.Customer,
      c.TotalUnits,
      c.Status AS CutStatus,
      c.CreatedAt,
      pm.idProMov,
      pm.ProMov AS ProMovNumber,
      pm.Fecha AS ProMovFecha,
      pm.Posteado AS ProMovPosteado,
      pm.idAlmacen AS ProMovAlmacen,
      CASE 
        WHEN pm.idProMov IS NOT NULL THEN 'REBAJADO'
        ELSE 'PENDIENTE'
      END AS TrimmingStatus
    FROM CutTickets c
    OUTER APPLY (
      SELECT TOP 1 p.idProMov, p.ProMov, p.Fecha, p.Posteado, p.idAlmacen
      FROM ProMov p
      WHERE p.Referencia = c.CutNumber
        AND p.Salida = 1
        AND p.idProMovTipo = 11
      ORDER BY p.Fecha DESC
    ) pm
    WHERE 1=1
  `;

  const request = pool.request();

  if (search && search.trim()) {
    request.input('search', sql.VarChar(100), `%${search.trim()}%`);
    query += ` AND (c.CutNumber LIKE @search OR c.Style LIKE @search OR c.Customer LIKE @search OR c.OrderNumber LIKE @search)`;
  }

  if (status && status.trim()) {
    request.input('cutStatus', sql.VarChar(50), status.trim());
    query += ` AND c.Status = @cutStatus`;
  }

  if (startDate) {
    request.input('startDate', sql.DateTime, new Date(startDate));
    query += ` AND c.CreatedAt >= @startDate`;
  }

  if (endDate) {
    request.input('endDate', sql.DateTime, new Date(endDate));
    query += ` AND c.CreatedAt <= @endDate`;
  }

  if (trimmingStatus === 'REBAJADO') {
    query += ` AND pm.idProMov IS NOT NULL`;
  } else if (trimmingStatus === 'PENDIENTE') {
    query += ` AND pm.idProMov IS NULL`;
  }

  query += ` ORDER BY c.IdCutTicket DESC`;

  const res = await request.query(query);
  return res.recordset;
}

/**
 * Obtiene el siguiente número de movimiento ProMov ejecutando spGetNextCounterSTR con fallback seguro.
 */
async function getNextProMovNumber(transaction) {
  try {
    const spReq = new sql.Request(transaction);
    spReq.input('XContador', sql.VarChar(16), 'General');
    spReq.output('OutPut', sql.VarChar(16));
    const spResult = await spReq.execute('spGetNextCounterSTR');
    if (spResult.output?.OutPut) {
      return spResult.output.OutPut.trim();
    }
  } catch (err) {
    console.warn('[Trimming] Error al ejecutar spGetNextCounterSTR, calculando siguiente ProMov vía MAX:', err.message);
  }

  // Fallback seguro: MAX(ProMov) + 1
  const maxReq = new sql.Request(transaction);
  const maxRes = await maxReq.query(`
    SELECT ISNULL(MAX(TRY_CAST(ProMov AS INT)), 4000) + 1 AS NextNum
    FROM ProMov
    WHERE ISNUMERIC(ProMov) = 1;
  `);

  return String(maxRes.recordset[0].NextNum);
}

/**
 * Genera la salida automática de inventario (ProMov y ProMovDet) en ERP SADE para un Cut Ticket.
 */
async function generateTrimmingOutput({ idCutTicket, items, idAlmacen = 'Stock', usuario = 'SWS_AUTO', postNow = false, notes = null }) {
  if (!idCutTicket) {
    throw new Error('El ID de la orden de corte (CutTicket) es obligatorio.');
  }

  if (!items || !Array.isArray(items) || items.length === 0) {
    throw new Error('Debe proporcionar al menos un artículo para generar la salida de trimmings.');
  }

  const pool = await getPool();
  const transaction = new sql.Transaction(pool);

  try {
    await transaction.begin();

    // 1. Obtener la orden de corte
    const ticketReq = new sql.Request(transaction);
    ticketReq.input('Id', sql.Int, idCutTicket);
    const ticketRes = await ticketReq.query(`SELECT * FROM CutTickets WHERE IdCutTicket = @Id;`);

    if (ticketRes.recordset.length === 0) {
      throw new Error(`Cut Ticket #${idCutTicket} no existe.`);
    }

    const ticket = ticketRes.recordset[0];
    const cutRef = ticket.CutNumber.trim();

    // 2. Verificar si ya existe una salida previa para evitar duplicados accidentales
    const checkReq = new sql.Request(transaction);
    checkReq.input('ref', sql.VarChar(20), cutRef);
    checkReq.input('idTipo', sql.Int, 11);
    const existing = await checkReq.query(`
      SELECT TOP 1 ProMov, idProMov FROM ProMov WHERE Referencia = @ref AND Salida = 1 AND idProMovTipo = @idTipo;
    `);

    if (existing.recordset.length > 0) {
      const prev = existing.recordset[0];
      throw new Error(`Ya existe una salida de materiales registrada para el corte ${cutRef} (Movimiento #${prev.ProMov}).`);
    }

    // 3. Generar número correlativo ProMov
    const proMovNumber = await getNextProMovNumber(transaction);

    // 4. Construir Concepto estándar ERP SADE: 'SALPRODUCCION - [CutNumber]- [Style]- [Qty] pcs'
    const cleanConcepto = `SALPRODUCCION - ${cutRef}- ${ticket.Style || ''}- ${ticket.TotalUnits || 0} pcs`.substring(0, 100);

    // 5. Insertar cabecera ProMov
    const movReq = new sql.Request(transaction);
    movReq.input('idProMovTipo', sql.Int, 11); // SAL PRODUCCION
    movReq.input('ProMov', sql.VarChar(16), proMovNumber);
    movReq.input('Referencia', sql.VarChar(20), cutRef.substring(0, 20));
    movReq.input('Concepto', sql.VarChar(100), cleanConcepto);
    movReq.input('Nota', sql.VarChar(500), notes ? notes.substring(0, 500) : null);
    movReq.input('idAlmacen', sql.VarChar(16), idAlmacen || 'Stock');
    movReq.input('Usuario', sql.VarChar(30), (usuario || 'SWS_AUTO').substring(0, 30));
    movReq.input('Posteado', sql.Bit, postNow ? 1 : 0);

    const movRes = await movReq.query(`
      DECLARE @newId UNIQUEIDENTIFIER = NEWID();
      INSERT INTO ProMov (
        idProMov, idProMovTipo, ProMov, Fecha, Salida, Referencia, Usuario,
        EntregadoPor, RecibidoPor, idAlmacen, Concepto, Nota, Posteado,
        PosteadoFecha, TotalITBIS, Hora, Impreso, Devolucion, Contabilizar, idCompania
      )
      OUTPUT INSERTED.idProMov, INSERTED.ProMov
      VALUES (
        @newId, @idProMovTipo, @ProMov, GETDATE(), 1, @Referencia, @Usuario,
        @Usuario, 'PRODUCCION', @idAlmacen, @Concepto, @Nota, @Posteado,
        CASE WHEN @Posteado = 1 THEN GETDATE() ELSE NULL END, 0, GETDATE(), 0, 0, 0, 1
      );
    `);

    const insertedMov = movRes.recordset[0];
    const idProMov = insertedMov.idProMov;

    // 6. Insertar detalle ProMovDet para cada accesorio
    let lineaIndex = 1;
    for (const item of items) {
      const cant = parseFloat(item.cantidadTotal);
      if (isNaN(cant) || cant <= 0) continue;

      const detReq = new sql.Request(transaction);
      detReq.input('idProMov', sql.UniqueIdentifier, idProMov);
      detReq.input('idProducto', sql.VarChar(25), String(item.idProducto).trim());
      detReq.input('Producto', sql.VarChar(120), String(item.producto || item.idProducto).substring(0, 120));
      detReq.input('Cantidad', sql.Decimal(18, 4), cant);
      detReq.input('Costo', sql.Decimal(18, 4), parseFloat(item.costo) || 0);
      detReq.input('idUnidad', sql.VarChar(16), String(item.idUnidad || 'Unidad').substring(0, 16));
      detReq.input('Posteado', sql.Bit, postNow ? 1 : 0);
      detReq.input('Linea', sql.Int, lineaIndex++);

      await detReq.query(`
        INSERT INTO ProMovDet (
          idProMovDet, idProMov, ProMovDet, idProducto, Producto, Cantidad,
          Costo, idUnidad, Posteado, XCosto, XCantidad, Linea, Referencia
        )
        VALUES (
          NEWID(), @idProMov, @Producto, @idProducto, @Producto, @Cantidad,
          @Costo, @idUnidad, @Posteado, 0, 0, @Linea, 'GENERAL'
        );
      `);
    }

    // 7. Registrar evento en historial WIP de la orden de corte
    const histReq = new sql.Request(transaction);
    histReq.input('IdCutTicket', sql.Int, idCutTicket);
    histReq.input('PreviousStatus', sql.VarChar(50), ticket.Status);
    histReq.input('NewStatus', sql.VarChar(50), ticket.Status); // Mantiene estatus WIP pero añade bitácora
    histReq.input('ChangedBy', sql.VarChar(100), usuario || 'SWS_AUTO');
    histReq.input('Notes', sql.NVarChar(500), `Salida de Trimmings ERP SADE generada con éxito: ProMov #${proMovNumber} (${items.length} accesorios).`);
    await histReq.query(`
      INSERT INTO CutTicketStatusHistory (IdCutTicket, PreviousStatus, NewStatus, ChangedBy, Notes)
      VALUES (@IdCutTicket, @PreviousStatus, @NewStatus, @ChangedBy, @Notes);
    `);

    await transaction.commit();

    return {
      success: true,
      idProMov,
      proMovNumber,
      cutNumber: cutRef,
      itemsCount: items.length,
      idAlmacen,
      posteado: postNow,
      message: `Salida de Trimmings #${proMovNumber} creada exitosamente en ERP SADE.`
    };
  } catch (err) {
    await transaction.rollback();
    throw err;
  }
}

/**
 * Consulta un movimiento ProMov y su detalle ProMovDet registrado en ERP SADE.
 */
async function getProMovDetails(idOrNumber) {
  const pool = await getPool();

  const movReq = new pool.request();
  movReq.input('param', sql.VarChar(50), String(idOrNumber).trim());

  const movRes = await movReq.query(`
    SELECT TOP 1 *
    FROM ProMov
    WHERE CAST(idProMov AS VARCHAR(50)) = @param OR ProMov = @param;
  `);

  if (movRes.recordset.length === 0) return null;

  const mov = movRes.recordset[0];

  const detReq = new pool.request();
  detReq.input('idProMov', sql.UniqueIdentifier, mov.idProMov);

  const detRes = await detReq.query(`
    SELECT 
      idProMovDet, idProducto, Producto, Cantidad, Costo, idUnidad, Posteado, Linea
    FROM ProMovDet
    WHERE idProMov = @idProMov
    ORDER BY Linea ASC, idProducto ASC;
  `);

  return {
    movement: mov,
    details: detRes.recordset
  };
}

module.exports = {
  searchProducts,
  matchStyleToProduct,
  explodeBOM,
  getExplosionData,
  getCutsTrimmingList,
  generateTrimmingOutput,
  getProMovDetails
};
