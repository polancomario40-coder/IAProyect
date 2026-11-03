-- =============================================================================
-- ACTUALIZACIÓN RETROACTIVA DE COSTOS EN PROMOVDET
-- Base de Datos: ERP (CBSVMO)
-- =============================================================================
SET NOCOUNT ON;

DECLARE @itbisOpt BIT = CONVERT(BIT, (SELECT Valor FROM Defaults WHERE clave = 'ITBIS_ENT_RECEP'));

BEGIN TRANSACTION;

BEGIN TRY
    -- Actualizar promovdet con el costo exacto de la orden de compra
    UPDATE pmd
    SET pmd.Costo = ROUND(((ISNULL(pe.CantidadRecibida, 0.00) * ISNULL(od.Costo, 0.00)) 
                    * (1.00 - (ISNULL(od.Descuento, 0.00) / 100.00)) 
                    * CASE WHEN ISNULL(@itbisOpt, 0) = 1 THEN (1.00 + (ISNULL(od.ITBIS, 0.00) / 100.00)) ELSE 1.00 END)
                    * ISNULL(dbo.fTasaActual(oc.idMoneda, pm.Fecha), 1.00), 2)
    FROM promovdet pmd
    INNER JOIN promov pm ON pmd.idProMov = pm.idProMov
    INNER JOIN prtEntradaCamion pe ON pm.ProMov = pe.ProMov
    INNER JOIN ocOrdenes oc ON pe.idOrden = oc.idOrden
    INNER JOIN ocDetalleOrden od ON oc.idOrden = od.idOrden 
        AND (od.idProducto = pe.idProducto OR LTRIM(RTRIM(od.idProducto)) = LTRIM(RTRIM(pe.idProducto)))
    WHERE pe.idOrden IS NOT NULL 
      AND (pmd.Costo = 0 OR pmd.Costo IS NULL)
      -- Descomentar la siguiente línea si deseas omitir los conduces de prueba:
      -- AND pe.Conduce NOT IN ('A123456');

    DECLARE @FilasActualizadas INT = @@ROWCOUNT;

    COMMIT TRANSACTION;

    PRINT 'Actualización completada exitosamente. Total de entradas valorizadas: ' + CAST(@FilasActualizadas AS VARCHAR(10));
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
