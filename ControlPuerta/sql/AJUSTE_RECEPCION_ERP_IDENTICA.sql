-- =====================================================================
-- AJUSTE RECEPCION ERP: Formato 100% idéntico a las generadas por SADE
-- Fecha: 18/09/2026
-- 1. IdTipoRecepcion = 'RECEPCION' (Muestra: "Recepcion de O/C")
-- 2. TipoReferencia  = 'CONDUCE'   (Muestra: "Conduce" en el combo)
-- 3. Referencia      = Conduce     (Número de conduce)
-- 4. Nota            = Conduce     (Caja de texto bajo Referencia)
-- 5. Suplidor        = Nombre del Suplidor
-- 6. ocRecepcionDet  = Lista todos los ítems de la OC (los que llegaron con su cantidad y los demás en 0)
--                      con Total = Cantidad comprada de la orden.
-- =====================================================================

CREATE OR ALTER PROCEDURE [dbo].[prtEjecutarCierreDia]
    @FechaDia       DATETIME,
    @UsuarioCierre  NVARCHAR(50),
    @Notas          NVARCHAR(500) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;

        DECLARE @idCierre UNIQUEIDENTIFIER = NEWID();
        DECLARE @totalRec INT = 0, @totalConOC INT = 0, @totalSinOC INT = 0;

        SELECT
            @totalRec   = COUNT(*),
            @totalConOC = SUM(CASE WHEN idOrden IS NOT NULL THEN 1 ELSE 0 END),
            @totalSinOC = SUM(CASE WHEN idOrden IS NULL     THEN 1 ELSE 0 END)
        FROM prtEntradaCamion
        WHERE CAST(FechaEntrada AS DATE) <= CAST(@FechaDia AS DATE)
          AND Status = 'RECIBIDO';
          
        IF OBJECT_ID('prtCierreDia') IS NOT NULL
        BEGIN
            INSERT INTO prtCierreDia (idCierre, FechaDia, FechaHoraCierre, UsuarioCierre, TotalRecepciones, TotalConOC, TotalSinOC, Notas)
            VALUES (@idCierre, CAST(@FechaDia AS DATE), GETDATE(), @UsuarioCierre, ISNULL(@totalRec,0), ISNULL(@totalConOC,0), ISNULL(@totalSinOC,0), @Notas);
        END

        DECLARE @idEntradaCamion UNIQUEIDENTIFIER;
        DECLARE @idOrden UNIQUEIDENTIFIER;
        DECLARE @OrdenNumero INT;
        DECLARE @idProducto VARCHAR(50);
        DECLARE @CantidadRecibida DECIMAL(18,4);
        DECLARE @idSuplidor VARCHAR(20);
        DECLARE @Suplidor VARCHAR(200);
        DECLARE @ProMov VARCHAR(20);
        DECLARE @idAlmacen VARCHAR(20);
        DECLARE @Conduce VARCHAR(100);
        DECLARE @EvalCalidad TINYINT, @EvalTiempo TINYINT, @EvalServicio TINYINT;

        DECLARE curEntradas CURSOR FOR
        SELECT idEntradaCamion, idOrden, OrdenNumero, idProducto, CantidadRecibida, idSuplidor, Suplidor, ProMov, EvalCalidad, EvalTiempo, EvalServicio, idAlmacen, Conduce
        FROM prtEntradaCamion
        WHERE CAST(FechaEntrada AS DATE) <= CAST(@FechaDia AS DATE)
          AND Status = 'RECIBIDO' AND idOrden IS NOT NULL;

        OPEN curEntradas;
        FETCH NEXT FROM curEntradas INTO @idEntradaCamion, @idOrden, @OrdenNumero, @idProducto, @CantidadRecibida, @idSuplidor, @Suplidor, @ProMov, @EvalCalidad, @EvalTiempo, @EvalServicio, @idAlmacen, @Conduce;

        WHILE @@FETCH_STATUS = 0
        BEGIN
            -- 1. Asegurar el Nombre del Suplidor (no el código numérico)
            IF @Suplidor IS NULL OR @Suplidor = '' OR ISNUMERIC(@Suplidor) = 1
            BEGIN
                SELECT TOP 1 @Suplidor = Nombre FROM cxpSuplidores WHERE idSuplidor = TRY_CAST(@idSuplidor AS INT);
            END

            -- 2. Si la entrada no tiene ProMov generado, generarlo primero
            IF @ProMov IS NULL OR @ProMov = ''
            BEGIN
                EXEC prtGenerarMovimientoEntrada @idEntradaCamion, @UsuarioCierre;
                SELECT @ProMov = ProMov FROM prtEntradaCamion WHERE idEntradaCamion = @idEntradaCamion;
            END

            -- 3. Identificar el ítem de la orden que corresponde al producto recibido
            DECLARE @MatchedDetId UNIQUEIDENTIFIER;
            SELECT TOP 1 @MatchedDetId = idDetalleOrden 
            FROM ocDetalleOrden 
            WHERE idOrden = @idOrden AND (idProducto = @idProducto OR LTRIM(RTRIM(idProducto)) = LTRIM(RTRIM(@idProducto)));

            IF @MatchedDetId IS NULL
            BEGIN
                SELECT TOP 1 @MatchedDetId = idDetalleOrden FROM ocDetalleOrden WHERE idOrden = @idOrden;
            END

            -- 4. Generar secuencia de recepción (RC No.)
            DECLARE @idRecepcion UNIQUEIDENTIFIER = NEWID();
            DECLARE @RecepcionSeq VARCHAR(20);
            SELECT @RecepcionSeq = CAST(ISNULL(MAX(CAST(Recepcion AS INT)), 0) + 1 AS VARCHAR) 
            FROM ocRecepcion WHERE ISNUMERIC(Recepcion) = 1;

            -- 5. Insertar cabecera en ocRecepcion idéntica a SADE ERP
            INSERT INTO ocRecepcion (
                idRecepcion,
                Recepcion,
                Fecha,
                idOrden,
                OrdenNo,
                Suplidor,
                Referencia,
                TipoReferencia, 
                Usuario,
                Status,
                FechaStatus,
                idAlmacen,
                Nota,
                EvalCalidad,
                EvalTiempo,
                EvalServicio,
                EvalOtros, 
                EntregadoPor,
                IdTipoRecepcion
            ) VALUES (
                @idRecepcion,
                @RecepcionSeq, 
                CAST(CAST(GETDATE() AS DATE) AS DATETIME),
                @idOrden,
                @OrdenNumero,
                ISNULL(@Suplidor, @idSuplidor),
                ISNULL(@Conduce, @ProMov),     -- Referencia (Conduce)
                'CONDUCE',                     -- TipoReferencia = 'CONDUCE' (se muestra en el combo)
                @UsuarioCierre,
                'A',
                CAST(CAST(GETDATE() AS DATE) AS DATETIME),
                ISNULL(@idAlmacen, 'GENERAL'),
                'Generado por Cierre Diario Puerta - Conduce: ' + ISNULL(@Conduce, ISNULL(@ProMov, '')) + CASE WHEN @Notas IS NOT NULL AND @Notas <> '' THEN ' - ' + @Notas ELSE '' END, -- Nota previa + Conduce
                ISNULL(@EvalCalidad, 4),
                ISNULL(@EvalTiempo, 0),
                ISNULL(@EvalServicio, 0),
                0,
                '',
                'RECEPCION'                    -- IdTipoRecepcion = 'RECEPCION' (se muestra "Recepcion de O/C")
            );

            -- 6. Insertar todos los ítems de la orden en ocRecepcionDet (el recibido con su cantidad, los demás en 0)
            INSERT INTO ocRecepcionDet (
                idRecepcionDet,
                idRecepcion,
                idDetalleOrden,
                TipoItem,
                idProducto,
                Cantidad,
                Rechazado,
                NotaSimple,
                CantidadTec,
                RechazadoTec,
                NotaTecnica,
                idUnidad,
                Descripcion,
                Usuario,
                Referencia,
                Total,
                idSolicitudDet
            )
            SELECT 
                NEWID(),
                @idRecepcion,
                od.idDetalleOrden,
                ISNULL(od.TipoItem, ''),
                od.idProducto,
                CASE 
                    WHEN od.idDetalleOrden = @MatchedDetId THEN ISNULL(@CantidadRecibida, 0)
                    ELSE 0 
                END,
                0,
                NULL,
                NULL,
                0,
                NULL,
                od.idUnidad,
                od.Descripcion,
                @UsuarioCierre,
                od.Referencia,
                od.Cantidad, -- Total comprado de la orden
                od.idSolicitudDet
            FROM ocDetalleOrden od
            WHERE od.idOrden = @idOrden;

            -- 7. Vincular promov con la recepción de la OC para que el ERP lo muestre en Movimientos de Almacén
            IF @ProMov IS NOT NULL AND @ProMov <> ''
            BEGIN
                UPDATE promov SET 
                    idReferencia  = @idRecepcion,
                    Conduce       = ISNULL(@Conduce, Conduce),
                    idOrdenCompra = @idOrden,
                    Concepto      = 'Entrada generada por O/C:' + CAST(@OrdenNumero AS VARCHAR(20)) + ' RECEPCION:#' + @RecepcionSeq
                WHERE ProMov = @ProMov;
            END

            -- 8. Actualizar entrada a CERRADO
            UPDATE prtEntradaCamion SET Status = 'CERRADO', idCierre = @idCierre,
                FechaCierre = GETDATE(), UsuarioCierre = @UsuarioCierre
            WHERE idEntradaCamion = @idEntradaCamion;

            FETCH NEXT FROM curEntradas INTO @idEntradaCamion, @idOrden, @OrdenNumero, @idProducto, @CantidadRecibida, @idSuplidor, @Suplidor, @ProMov, @EvalCalidad, @EvalTiempo, @EvalServicio, @idAlmacen, @Conduce;
        END
        CLOSE curEntradas;
        DEALLOCATE curEntradas;

        COMMIT TRANSACTION;

        SELECT @idCierre AS idCierre, ISNULL(@totalRec,0) AS TotalRecepciones,
               ISNULL(@totalConOC,0) AS TotalConOC, ISNULL(@totalSinOC,0) AS TotalSinOC;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

-- ---------------------------------------------------------------------
-- ACTUALIZACIÓN RETROACTIVA DE RECEPCIONES EXISTENTES GENERADAS POR PUERTA
-- ---------------------------------------------------------------------

-- A. Actualizar cabeceras en ocRecepcion
UPDATE r
SET 
    r.IdTipoRecepcion = 'RECEPCION',
    r.TipoReferencia  = 'CONDUCE',
    r.Referencia      = ISNULL(e.Conduce, r.Referencia),
    r.Nota            = 'Generado por Cierre Diario Puerta - Conduce: ' + ISNULL(e.Conduce, ISNULL(r.Referencia, ''))
FROM ocRecepcion r
INNER JOIN prtEntradaCamion e ON (r.Referencia = e.ProMov OR r.idOrden = e.idOrden)
WHERE r.TipoReferencia IN ('PRT', 'CONDUCE');

-- B. Actualizar Total (Cantidad comprada) en ocRecepcionDet
UPDATE rd
SET rd.Total = od.Cantidad,
    rd.idSolicitudDet = od.idSolicitudDet
FROM ocRecepcionDet rd
INNER JOIN ocDetalleOrden od ON rd.idDetalleOrden = od.idDetalleOrden
INNER JOIN ocRecepcion r ON rd.idRecepcion = r.idRecepcion
WHERE r.TipoReferencia IN ('PRT', 'CONDUCE');

-- C. Insertar en ocRecepcionDet los ítems de la OC que faltaban con Cantidad = 0
INSERT INTO ocRecepcionDet (
    idRecepcionDet, idRecepcion, idDetalleOrden, TipoItem, idProducto, Cantidad, Rechazado,
    CantidadTec, RechazadoTec, idUnidad, Descripcion, Usuario, Referencia, Total, idSolicitudDet
)
SELECT 
    NEWID(),
    r.idRecepcion,
    od.idDetalleOrden,
    ISNULL(od.TipoItem, ''),
    od.idProducto,
    0,
    0,
    NULL,
    0,
    od.idUnidad,
    od.Descripcion,
    r.Usuario,
    od.Referencia,
    od.Cantidad,
    od.idSolicitudDet
FROM ocRecepcion r
INNER JOIN ocDetalleOrden od ON r.idOrden = od.idOrden
WHERE r.TipoReferencia = 'CONDUCE'
  AND NOT EXISTS (
      SELECT 1 FROM ocRecepcionDet d WHERE d.idRecepcion = r.idRecepcion AND d.idDetalleOrden = od.idDetalleOrden
  );
GO
