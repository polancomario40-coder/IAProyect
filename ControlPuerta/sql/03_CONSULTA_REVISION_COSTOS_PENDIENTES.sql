-- =============================================================================
-- REVISIÓN DE ENTRADAS DE ALMACÉN SIN COSTO (CONTROL DE PUERTA)
-- Base de Datos: ERP (CBSVMO)
-- =============================================================================
DECLARE @itbisOpt BIT = CONVERT(BIT, (SELECT Valor FROM Defaults WHERE clave = 'ITBIS_ENT_RECEP'));

SELECT 
    pm.ProMov,
    pe.FechaEntrada,
    pe.Conduce,
    pe.Placa,
    pe.Suplidor,
    pe.OrdenNumero AS OC_Numero,
    pmd.idProducto,
    pmd.Producto,
    pe.CantidadRecibida AS Cantidad_OC,
    pe.idUnidad AS Unidad_OC,
    pmd.Cantidad AS Cantidad_Almacen,
    pmd.idUnidad AS Unidad_Almacen,
    od.Costo AS Costo_Unitario_OC,
    oc.idMoneda,
    dbo.fTasaActual(oc.idMoneda, pm.Fecha) AS Tasa_Cambio,
    pmd.Costo AS Costo_Actual_Promov,
    -- Cálculo idéntico al procedimiento ocRecepcion2ProMov del ERP
    ROUND(((ISNULL(pe.CantidadRecibida, 0.00) * ISNULL(od.Costo, 0.00)) 
       * (1.00 - (ISNULL(od.Descuento, 0.00) / 100.00)) 
       * CASE WHEN ISNULL(@itbisOpt, 0) = 1 THEN (1.00 + (ISNULL(od.ITBIS, 0.00) / 100.00)) ELSE 1.00 END)
       * ISNULL(dbo.fTasaActual(oc.idMoneda, pm.Fecha), 1.00), 2) AS Costo_Calculado_Nuevo,
    CASE 
        WHEN pe.Conduce LIKE '%A123456%' OR pe.Conduce LIKE '%TEST%' OR pe.Conduce LIKE '%PRUEBA%' THEN 'POSIBLE PRUEBA'
        ELSE 'REAL'
    END AS Tipo_Registro,
    pm.Concepto
FROM promov pm
INNER JOIN promovdet pmd ON pm.idProMov = pmd.idProMov
INNER JOIN prtEntradaCamion pe ON pm.ProMov = pe.ProMov
INNER JOIN ocOrdenes oc ON pe.idOrden = oc.idOrden
LEFT JOIN ocDetalleOrden od ON oc.idOrden = od.idOrden 
    AND (od.idProducto = pe.idProducto OR LTRIM(RTRIM(od.idProducto)) = LTRIM(RTRIM(pe.idProducto)))
WHERE pe.idOrden IS NOT NULL 
  AND (pmd.Costo = 0 OR pmd.Costo IS NULL)
ORDER BY pe.FechaEntrada DESC;
