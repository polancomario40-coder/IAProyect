-- =============================================================================
-- PROCEDIMIENTOS ALMACENADOS DEFINITIVOS CON CÁLCULO DE COSTO EN ENTRADAS
-- Base de Datos: ERP (CBSVMO)
-- =============================================================================

SET NOCOUNT ON;
GO

-- 1. Actualizar prtGenerarMovimientoEntrada
CREATE OR ALTER PROCEDURE dbo.prtGenerarMovimientoEntrada
    @idEntradaCamion UNIQUEIDENTIFIER,
    @Usuario VARCHAR(100)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @idSuplidor VARCHAR(15), @Suplidor VARCHAR(200), @idAlmacen VARCHAR(20), @Referencia VARCHAR(100), @Placa VARCHAR(20);
    DECLARE @idProducto VARCHAR(50), @Producto VARCHAR(200), @Cantidad DECIMAL(18,4), @CantidadRecibidaOC DECIMAL(18,4);
    DECLARE @idUnidad VARCHAR(20);
    DECLARE @idOrden UNIQUEIDENTIFIER, @OrdenNumero INT;
    DECLARE @Fecha DATETIME = GETDATE();

    SELECT 
        @idSuplidor = idSuplidor, 
        @Suplidor = Suplidor, 
        @idAlmacen = ISNULL(idAlmacen, 'GENERAL'),
        @Referencia = Conduce,
        @Placa = Placa,
        @idProducto = idProducto,
        @Producto = Producto,
        @Cantidad = ISNULL(CantidadAlmacen, CantidadRecibida),
        @CantidadRecibidaOC = ISNULL(CantidadRecibida, CantidadAlmacen),
        @idUnidad = ISNULL(idUnidadAlmacen, ISNULL(idUnidad, 'UND')),
        @idOrden = idOrden,
        @OrdenNumero = OrdenNumero
    FROM prtEntradaCamion 
    WHERE idEntradaCamion = @idEntradaCamion;

    IF NOT EXISTS(SELECT 1 FROM Almacen WHERE idAlmacen = @idAlmacen)
    BEGIN
        SELECT TOP 1 @idAlmacen = Valor FROM ConfiguracionPC WHERE Configuracion = 'ALMACENDEFAULT';
        IF @idAlmacen IS NULL OR NOT EXISTS(SELECT 1 FROM Almacen WHERE idAlmacen = @idAlmacen)
            SET @idAlmacen = 'GENERAL';
    END

    -- Calcular costo si tiene orden de compra asociada
    DECLARE @CostoTotal DECIMAL(18,2) = 0.00;
    IF @idOrden IS NOT NULL
    BEGIN
        DECLARE @CostoOC DECIMAL(18,4) = 0.00, @DescOC DECIMAL(18,4) = 0.00, @ItbisOC DECIMAL(18,4) = 0.00;
        SELECT TOP 1 
            @CostoOC = ISNULL(od.Costo, 0.00),
            @DescOC = ISNULL(od.Descuento, 0.00),
            @ItbisOC = ISNULL(od.ITBIS, 0.00)
        FROM ocDetalleOrden od
        WHERE od.idOrden = @idOrden 
          AND (od.idProducto = @idProducto OR LTRIM(RTRIM(od.idProducto)) = LTRIM(RTRIM(@idProducto)));

        IF @CostoOC = 0.00
        BEGIN
            SELECT TOP 1 
                @CostoOC = ISNULL(od.Costo, 0.00),
                @DescOC = ISNULL(od.Descuento, 0.00),
                @ItbisOC = ISNULL(od.ITBIS, 0.00)
            FROM ocDetalleOrden od
            WHERE od.idOrden = @idOrden;
        END

        DECLARE @idMonedaOC INT = 1;
        SELECT TOP 1 @idMonedaOC = ISNULL(idMoneda, 1) FROM ocOrdenes WHERE idOrden = @idOrden;

        DECLARE @itbisOpt BIT = CONVERT(BIT, (SELECT Valor FROM Defaults WHERE clave = 'ITBIS_ENT_RECEP'));
        DECLARE @TasaOC DECIMAL(18,4) = ISNULL(dbo.fTasaActual(@idMonedaOC, @Fecha), 1.00);
        IF @TasaOC <= 0 SET @TasaOC = 1.00;

        SET @CostoTotal = ROUND(((ISNULL(@CantidadRecibidaOC, 0.00) * @CostoOC) * (1.00 - (@DescOC / 100.00))
                          * CASE WHEN ISNULL(@itbisOpt, 0) = 1 THEN (1.00 + (@ItbisOC / 100.00)) ELSE 1.00 END)
                          * @TasaOC, 2);
    END

    -- Si ya tiene ProMov asignado y existe en promov, actualizar y no duplicar
    DECLARE @ExistingProMov VARCHAR(20);
    SELECT @ExistingProMov = ProMov FROM prtEntradaCamion WHERE idEntradaCamion = @idEntradaCamion;
    IF @ExistingProMov IS NOT NULL AND @ExistingProMov <> '' AND EXISTS(SELECT 1 FROM promov WHERE ProMov = @ExistingProMov)
    BEGIN
        UPDATE promov 
        SET Conduce = ISNULL(@Referencia, Conduce),
            idOrdenCompra = ISNULL(@idOrden, idOrdenCompra)
        WHERE ProMov = @ExistingProMov;

        IF @CostoTotal > 0
        BEGIN
            UPDATE d
            SET d.Costo = @CostoTotal
            FROM promovdet d
            INNER JOIN promov p ON d.idProMov = p.idProMov
            WHERE p.ProMov = @ExistingProMov AND (d.Costo = 0 OR d.Costo IS NULL);
        END
        RETURN;
    END

    DECLARE @idProMovTipo INT = 1; 
    DECLARE @ProMovNum INT;
    SELECT @ProMovNum = ISNULL(MAX(TRY_CAST(ProMov AS INT)), 0) + 1 FROM promov WHERE ISNUMERIC(ProMov) = 1;
    DECLARE @ProMov VARCHAR(20) = CAST(@ProMovNum AS VARCHAR(20));

    -- Formato unificado de Concepto
    DECLARE @Concepto VARCHAR(200);
    IF @OrdenNumero IS NOT NULL
        SET @Concepto = 'Entrada por Conduce: ' + ISNULL(@Referencia,'') + ' - O/C: ' + CAST(@OrdenNumero AS VARCHAR(20));
    ELSE
        SET @Concepto = 'Entrada por Conduce: ' + ISNULL(@Referencia,'') + ' - Placa: ' + ISNULL(@Placa,'');

    DECLARE @idProMov UNIQUEIDENTIFIER = NEWID();
    INSERT INTO promov (
        idProMov, idProMovTipo, ProMov, Fecha, Salida, Referencia, Conduce,
        Usuario, RecibidoPor, idAlmacen, Concepto, Nota, idSuplidor, Suplidor, Hora, Posteado,
        idOrdenCompra
    )
    VALUES (
        @idProMov, @idProMovTipo, @ProMov, CAST(@Fecha AS DATE), 0, @Referencia, @Referencia,
        @Usuario, @Usuario, @idAlmacen, @Concepto, 'Generado automáticamente por Control de Puerta', 
        @idSuplidor, @Suplidor, @Fecha, 0,
        @idOrden
    );

    DECLARE @idProMovDet UNIQUEIDENTIFIER = NEWID();
    INSERT INTO promovdet (
        idProMovDet, idProMov, idProducto, Producto, Cantidad, Costo, idUnidad, Posteado
    )
    VALUES (
        @idProMovDet, @idProMov, @idProducto, @Producto, @Cantidad, @CostoTotal, @idUnidad, 0
    );

    UPDATE Almacen 
    SET ContadorEntradas = CAST(ISNULL(TRY_CAST(ContadorEntradas AS INT), 0) + 1 AS VARCHAR) 
    WHERE idAlmacen = @idAlmacen;

    UPDATE prtEntradaCamion
    SET ProMov = @ProMov
    WHERE idEntradaCamion = @idEntradaCamion;
END;
GO

-- 2. Actualizar prtEjecutarCierreDia
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
                'Generado por Cierre Diario Puerta - Conduce: ' + ISNULL(@Conduce, ISNULL(@ProMov, '')) + CASE WHEN @Notas IS NOT NULL AND @Notas <> '' THEN ' - ' + @Notas ELSE '' END,
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

            -- 7. Vincular promov con formato unificado y actualizar Costo en promovdet
            IF @ProMov IS NOT NULL AND @ProMov <> ''
            BEGIN
                UPDATE promov SET 
                    idReferencia  = @idRecepcion,
                    Conduce       = ISNULL(@Conduce, Conduce),
                    idOrdenCompra = @idOrden,
                    Concepto      = 'Entrada por Conduce: ' + ISNULL(@Conduce, ISNULL(Conduce, '')) + ' - O/C: ' + CAST(@OrdenNumero AS VARCHAR(20)) + ' (REC:#' + @RecepcionSeq + ')'
                WHERE ProMov = @ProMov;

                -- Cálculo y actualización de costo idéntico a ocRecepcion2ProMov
                DECLARE @itbisOptCierre BIT = CONVERT(BIT, (SELECT Valor FROM Defaults WHERE clave = 'ITBIS_ENT_RECEP'));

                UPDATE d
                SET d.Costo = ROUND(((ISNULL(@CantidadRecibida, 0.00) * ISNULL(od.Costo, 0.00)) 
                              * (1.00 - (ISNULL(od.Descuento, 0.00) / 100.00)) 
                              * CASE WHEN ISNULL(@itbisOptCierre, 0) = 1 THEN (1.00 + (ISNULL(od.ITBIS, 0.00) / 100.00)) ELSE 1.00 END)
                              * ISNULL(dbo.fTasaActual(oc.idMoneda, CAST(@FechaDia AS DATE)), 1.00), 2)
                FROM promovdet d
                INNER JOIN promov p ON d.idProMov = p.idProMov
                LEFT JOIN ocDetalleOrden od ON od.idDetalleOrden = @MatchedDetId
                LEFT JOIN ocOrdenes oc ON oc.idOrden = @idOrden
                WHERE p.ProMov = @ProMov
                  AND (d.Costo = 0 OR d.Costo IS NULL);
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
