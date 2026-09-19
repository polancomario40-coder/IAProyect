-- =============================================================================
-- SCRIPT CONSOLIDADO Y ACTUALIZADO PARA BASE DE DATOS DE PRODUCCIÓN
-- Control de Puerta y Recepción de Agregados
-- Fecha de actualización: 2026-09-11
-- =============================================================================

-- =============================================================================
-- PARTE 1: BASE DE DATOS PRINCIPAL / ERP (Ej. cbsvmotest / Producción)
-- =============================================================================
-- USE [TuBaseDeDatosERP];
-- GO

-- 1.1 Columnas requeridas en prtEntradaCamion (incluyendo las nuevas de conversión de unidades)
IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'prtEntradaCamion' AND COLUMN_NAME = 'ConduceTransporte')
BEGIN
    ALTER TABLE prtEntradaCamion ADD ConduceTransporte VARCHAR(50) NULL;
    PRINT 'Agregada columna ConduceTransporte a prtEntradaCamion';
END;
GO

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'prtEntradaCamion' AND COLUMN_NAME = 'idUnidad')
BEGIN
    ALTER TABLE prtEntradaCamion ADD idUnidad VARCHAR(20) NULL;
    PRINT 'Agregada columna idUnidad a prtEntradaCamion';
END;
GO

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'prtEntradaCamion' AND COLUMN_NAME = 'idUnidadAlmacen')
BEGIN
    ALTER TABLE prtEntradaCamion ADD idUnidadAlmacen VARCHAR(20) NULL;
    PRINT 'Agregada columna idUnidadAlmacen a prtEntradaCamion';
END;
GO

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'prtEntradaCamion' AND COLUMN_NAME = 'CantidadAlmacen')
BEGIN
    ALTER TABLE prtEntradaCamion ADD CantidadAlmacen DECIMAL(18,4) NULL;
    PRINT 'Agregada columna CantidadAlmacen a prtEntradaCamion';
END;
GO


-- 1.2 Tabla de Secuencia Automática por Almacén
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'prtSecuenciaAlmacen')
BEGIN
    CREATE TABLE prtSecuenciaAlmacen (
        idAlmacen VARCHAR(20) NOT NULL PRIMARY KEY,
        UltimaSecuencia INT NOT NULL DEFAULT 0,
        FechaModificacion DATETIME NOT NULL DEFAULT GETDATE()
    );
    PRINT 'Tabla prtSecuenciaAlmacen creada exitosamente.';
END;
GO


-- 1.3 Procedimiento para Generar la Siguiente Secuencia por Almacén
CREATE OR ALTER PROCEDURE prtObtenerSiguienteSecuenciaAlmacen
    @idAlmacen VARCHAR(20),
    @SecuenciaGenerada VARCHAR(50) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET @idAlmacen = LTRIM(RTRIM(ISNULL(@idAlmacen, 'GENERAL')));

    DECLARE @NextSeq INT;

    IF NOT EXISTS (SELECT 1 FROM prtSecuenciaAlmacen WITH (UPDLOCK, HOLDLOCK) WHERE idAlmacen = @idAlmacen)
    BEGIN
        INSERT INTO prtSecuenciaAlmacen (idAlmacen, UltimaSecuencia, FechaModificacion)
        VALUES (@idAlmacen, 0, GETDATE());
    END

    UPDATE prtSecuenciaAlmacen WITH (UPDLOCK, ROWLOCK)
    SET @NextSeq = UltimaSecuencia = UltimaSecuencia + 1,
        FechaModificacion = GETDATE()
    WHERE idAlmacen = @idAlmacen;

    -- Formato: [ALMACEN]-[00001]
    SET @SecuenciaGenerada = @idAlmacen + '-' + RIGHT('00000' + CAST(@NextSeq AS VARCHAR(10)), 5);
END;
GO


-- 1.4 Procedimiento para Generar Movimiento de Entrada (Inventario)
-- Actualizado para tomar en cuenta la unidad del almacén y la cantidad convertida (ej. Toneladas -> Fundas)
CREATE OR ALTER PROCEDURE prtGenerarMovimientoEntrada
    @idEntradaCamion UNIQUEIDENTIFIER,
    @Usuario VARCHAR(100)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @idSuplidor VARCHAR(15), @Suplidor VARCHAR(200), @idAlmacen VARCHAR(20), @Referencia VARCHAR(100), @Placa VARCHAR(20);
    DECLARE @idProducto VARCHAR(50), @Producto VARCHAR(200), @Cantidad DECIMAL(18,4);
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

    -- Si ya tiene ProMov asignado y existe en promov, actualizar y no duplicar
    DECLARE @ExistingProMov VARCHAR(20);
    SELECT @ExistingProMov = ProMov FROM prtEntradaCamion WHERE idEntradaCamion = @idEntradaCamion;
    IF @ExistingProMov IS NOT NULL AND @ExistingProMov <> '' AND EXISTS(SELECT 1 FROM promov WHERE ProMov = @ExistingProMov)
    BEGIN
        UPDATE promov 
        SET Conduce = ISNULL(@Referencia, Conduce),
            idOrdenCompra = ISNULL(@idOrden, idOrdenCompra)
        WHERE ProMov = @ExistingProMov;
        RETURN;
    END

    DECLARE @idProMovTipo INT = 1; 
    DECLARE @ProMovNum INT;
    SELECT @ProMovNum = ISNULL(MAX(TRY_CAST(ProMov AS INT)), 0) + 1 FROM promov WHERE ISNUMERIC(ProMov) = 1;
    DECLARE @ProMov VARCHAR(20) = CAST(@ProMovNum AS VARCHAR(20));

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
        @idProMovDet, @idProMov, @idProducto, @Producto, @Cantidad, 0, @idUnidad, 0
    );

    UPDATE Almacen 
    SET ContadorEntradas = CAST(ISNULL(TRY_CAST(ContadorEntradas AS INT), 0) + 1 AS VARCHAR) 
    WHERE idAlmacen = @idAlmacen;

    UPDATE prtEntradaCamion
    SET ProMov = @ProMov
    WHERE idEntradaCamion = @idEntradaCamion;
END;
GO


-- 1.5 Parámetros de Configuración ISO en la tabla Defaults
IF NOT EXISTS (SELECT 1 FROM Defaults WHERE Categoria = 'ISO' AND Clave = 'CONDUCE_FORMATO')
BEGIN
    INSERT INTO Defaults (Categoria, Clave, Descripcion, Valor)
    VALUES ('ISO', 'CONDUCE_FORMATO', 'Formulario Conduce Control Puerta', 'FE-GC-02|03');
    PRINT 'Configuración ISO insertada en tabla Defaults';
END
ELSE
BEGIN
    UPDATE Defaults 
    SET Valor = 'FE-GC-02|03'
    WHERE Categoria = 'ISO' AND Clave = 'CONDUCE_FORMATO';
    PRINT 'Configuración ISO actualizada en tabla Defaults';
END;
GO

-- 1.6 Procedimiento de Cierre de Día (actualizado para vincular promov con ocRecepcion)
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
            -- Asegurar el Nombre del Suplidor (no el código numérico)
            IF @Suplidor IS NULL OR @Suplidor = '' OR ISNUMERIC(@Suplidor) = 1
            BEGIN
                SELECT TOP 1 @Suplidor = Nombre FROM cxpSuplidores WHERE idSuplidor = TRY_CAST(@idSuplidor AS INT);
            END

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
                    Concepto      = 'Entrada por Conduce: ' + ISNULL(@Conduce, ISNULL(Conduce, '')) + ' - O/C: ' + CAST(@OrdenNumero AS VARCHAR(20)) + ' (REC:#' + @RecepcionSeq + ')'
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



-- =============================================================================
-- PARTE 2: BASE DE DATOS DE EVIDENCIAS (SADE_Evidencias)
-- =============================================================================
-- USE [SADE_Evidencias];
-- GO

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Evidencias' AND COLUMN_NAME = 'FotoCamion')
BEGIN
    ALTER TABLE Evidencias ADD FotoCamion VARBINARY(MAX) NULL;
    PRINT 'Agregada columna FotoCamion a tabla Evidencias';
END;
GO

-- Procedimiento evGuardarEvidencia actualizado con FotoCamion
CREATE OR ALTER PROCEDURE evGuardarEvidencia
    @IdRefExterna       UNIQUEIDENTIFIER = NULL,
    @Referencia         VARCHAR(100)     = NULL,
    @FotoConduce        VARBINARY(MAX)   = NULL,
    @FotoConduceMime    VARCHAR(50)      = NULL,
    @FotoConduceNombre  VARCHAR(200)     = NULL,
    @FirmaDigital       VARBINARY(MAX)   = NULL,
    @ImagenFirmada      VARBINARY(MAX)   = NULL,
    @FotoCamion         VARBINARY(MAX)   = NULL,
    @MetadatosJson      NVARCHAR(MAX)    = NULL,
    @Usuario            VARCHAR(100)     = NULL,
    @IpTerminal         VARCHAR(50)      = NULL,
    @NuevoId            UNIQUEIDENTIFIER OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    SET @NuevoId = NEWID();

    INSERT INTO Evidencias (
        IdEvidencia, IdRefExterna, Referencia,
        FotoConduce, FotoConduceMime, FotoConduceNombre,
        FirmaDigital, ImagenFirmada, FotoCamion,
        MetadatosJson, Usuario, IpTerminal, FechaCreacion
    )
    VALUES (
        @NuevoId, @IdRefExterna, @Referencia,
        @FotoConduce, @FotoConduceMime, @FotoConduceNombre,
        @FirmaDigital, @ImagenFirmada, @FotoCamion,
        @MetadatosJson, @Usuario, @IpTerminal, GETDATE()
    );
END;
GO
