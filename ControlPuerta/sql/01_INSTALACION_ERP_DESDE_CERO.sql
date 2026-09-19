-- =============================================================================
-- CONTROL DE PUERTA Y RECEPCIÓN DE AGREGADOS (SADE ERP)
-- SCRIPT ÚNICO DE INSTALACIÓN COMPLETA DESDE CERO
-- Base de Datos: ERP (Ej. CBSVMO / CBSVMOTEST / Nueva BD)
-- =============================================================================
-- INSTRUCCIONES:
-- 1. Abra este script en SQL Server Management Studio (SSMS).
-- 2. Asegúrese de seleccionar la base de datos ERP destino arriba.
-- 3. Ejecute el script completo. Es idempotente (se puede correr varias veces de forma segura).
-- =============================================================================

SET NOCOUNT ON;

-- =============================================================================
-- 1. TABLAS PRINCIPALES
-- =============================================================================

-- 1.1 Tabla de Puertas Físicas
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'prtPuerta')
BEGIN
    CREATE TABLE prtPuerta (
        idPuerta        VARCHAR(16)     NOT NULL PRIMARY KEY,
        Puerta          NVARCHAR(100)   NOT NULL,
        idAlmacen       VARCHAR(20)     NULL,
        Activo          BIT             NOT NULL DEFAULT 1,
        FechaCreacion   DATETIME        NOT NULL DEFAULT GETDATE()
    );
    PRINT 'Tabla prtPuerta creada.';
END;
GO

-- 1.2 Tabla de Cierres Diarios
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'prtCierreDia')
BEGIN
    CREATE TABLE prtCierreDia (
        idCierre            UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_prtCierreDia PRIMARY KEY DEFAULT NEWID(),
        FechaDia            DATE             NOT NULL,
        FechaHoraCierre     DATETIME2(0)     NOT NULL DEFAULT GETDATE(),
        UsuarioCierre       NVARCHAR(50)     NOT NULL,
        TotalRecepciones    INT              NOT NULL DEFAULT 0,
        TotalConOC          INT              NOT NULL DEFAULT 0,
        TotalSinOC          INT              NOT NULL DEFAULT 0,
        Notas               NVARCHAR(500)    NULL,
        CONSTRAINT UQ_prtCierreDia_FechaDia UNIQUE (FechaDia)
    );
    PRINT 'Tabla prtCierreDia creada.';
END;
GO

-- 1.3 Tabla Principal: prtEntradaCamion
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'prtEntradaCamion')
BEGIN
    CREATE TABLE prtEntradaCamion (
        idEntradaCamion     UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_prtEntradaCamion PRIMARY KEY DEFAULT NEWID(),
        Conduce             NVARCHAR(50)     NOT NULL,
        ConduceTransporte   VARCHAR(50)      NULL,
        FechaEntrada        DATETIME2(0)     NOT NULL DEFAULT GETDATE(),

        -- Transportista y Vehículo
        idTransportista     VARCHAR(16)      NULL,
        Transportista       NVARCHAR(200)    NULL,
        Placa               NVARCHAR(20)     NOT NULL,
        PlacaOcrTexto       NVARCHAR(50)     NULL,
        PlacaOcrConfianza   DECIMAL(5,4)     NULL,

        -- Chofer
        idChofer            UNIQUEIDENTIFIER NULL,
        NombreChofer        NVARCHAR(100)    NULL,

        -- Recepción Almacén
        FechaRecepcion      DATETIME2(0)     NULL,
        UsuarioRecepcion    NVARCHAR(50)     NULL,
        idAlmacen           VARCHAR(20)      NULL,

        -- Suplidor
        idSuplidor          VARCHAR(20)      NULL,
        Suplidor            NVARCHAR(200)    NULL,

        -- Producto Resumen / Principal
        idProducto          VARCHAR(50)      NULL,
        Producto            NVARCHAR(200)    NULL,
        CantidadDeclarada   DECIMAL(18,4)    NULL,
        CantidadRecibida    DECIMAL(18,4)    NULL,
        idUnidad            VARCHAR(20)      NULL,
        idUnidadAlmacen     VARCHAR(20)      NULL,
        CantidadAlmacen     DECIMAL(18,4)    NULL,

        -- Enlace con Inventario y Compras ERP
        ProMov              VARCHAR(20)      NULL,
        idOrden             UNIQUEIDENTIFIER NULL,
        OrdenNumero         INT              NULL,
        idEvidencia         UNIQUEIDENTIFIER NULL,

        -- Evaluaciones de Calidad del Suplidor
        EvalCalidad         TINYINT          NULL DEFAULT 4,
        EvalTiempo          TINYINT          NULL DEFAULT 0,
        EvalServicio        TINYINT          NULL DEFAULT 0,

        -- Control y Estado
        idPuerta            VARCHAR(16)      NULL,
        Notas               NVARCHAR(500)    NULL,
        Status              VARCHAR(20)      NOT NULL DEFAULT 'PENDIENTE',

        -- Auditoría
        Usuario             NVARCHAR(50)     NOT NULL,
        FechaCreacion       DATETIME2(0)     NOT NULL DEFAULT GETDATE(),
        FechaModificacion   DATETIME2(0)     NULL,
        UsuarioModificacion NVARCHAR(50)     NULL,

        -- Cierre Diario
        idCierre            UNIQUEIDENTIFIER NULL CONSTRAINT FK_prtEntradaCamion_Cierre REFERENCES prtCierreDia(idCierre),
        FechaCierre         DATETIME2(0)     NULL,
        UsuarioCierre       NVARCHAR(50)     NULL
    );

    CREATE INDEX IX_prtEntradaCamion_Conduce      ON prtEntradaCamion (Conduce);
    CREATE INDEX IX_prtEntradaCamion_Placa        ON prtEntradaCamion (Placa);
    CREATE INDEX IX_prtEntradaCamion_FechaEntrada ON prtEntradaCamion (FechaEntrada);
    CREATE INDEX IX_prtEntradaCamion_Status       ON prtEntradaCamion (Status);
    CREATE INDEX IX_prtEntradaCamion_ProMov       ON prtEntradaCamion (ProMov);

    PRINT 'Tabla prtEntradaCamion creada.';
END;
GO

-- 1.4 Tabla Detalle de Productos por Entrada (Multi-producto)
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'prtEntradaDetalle')
BEGIN
    CREATE TABLE prtEntradaDetalle (
        idEntradaDetalle    UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_prtEntradaDetalle PRIMARY KEY DEFAULT NEWID(),
        idEntradaCamion     UNIQUEIDENTIFIER NOT NULL CONSTRAINT FK_prtEntradaDetalle_Entrada
                                                 REFERENCES prtEntradaCamion(idEntradaCamion) ON DELETE CASCADE,
        idProducto          VARCHAR(50)      NULL,
        Producto            NVARCHAR(200)    NULL,
        Cantidad            DECIMAL(18,4)    NULL,
        idUnidad            VARCHAR(20)      NULL,
        Notas               NVARCHAR(300)    NULL,
        Orden               INT              NOT NULL DEFAULT 1
    );

    CREATE INDEX IX_prtEntradaDetalle_Entrada ON prtEntradaDetalle (idEntradaCamion);
    PRINT 'Tabla prtEntradaDetalle creada.';
END;
GO

-- 1.5 Tabla de Secuencias Automáticas por Almacén (Conduce Transporte)
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'prtSecuenciaAlmacen')
BEGIN
    CREATE TABLE prtSecuenciaAlmacen (
        idAlmacen           VARCHAR(20) NOT NULL PRIMARY KEY,
        UltimaSecuencia     INT         NOT NULL DEFAULT 0,
        FechaModificacion   DATETIME    NOT NULL DEFAULT GETDATE()
    );
    PRINT 'Tabla prtSecuenciaAlmacen creada.';
END;
GO

-- 1.6 Tabla de Choferes Genéricos
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'prtChoferesGenericos')
BEGIN
    CREATE TABLE prtChoferesGenericos (
        idChoferGenerico    INT IDENTITY(1,1) PRIMARY KEY,
        idTransportista     VARCHAR(20)  NOT NULL,
        NombreChofer        VARCHAR(150) NOT NULL,
        Licencia            VARCHAR(50)  NULL,
        Activo              BIT          NOT NULL DEFAULT 1,
        FechaCreacion       DATETIME     NOT NULL DEFAULT GETDATE()
    );
    PRINT 'Tabla prtChoferesGenericos creada.';
END;
GO


-- =============================================================================
-- 2. PARÁMETROS ISO Y CONFIGURACIÓN BASE
-- =============================================================================

-- Parámetro de Formato de Conduce ISO en tabla Defaults
IF NOT EXISTS (SELECT 1 FROM Defaults WHERE Categoria = 'ISO' AND Clave = 'CONDUCE_FORMATO')
BEGIN
    INSERT INTO Defaults (Categoria, Clave, Descripcion, Valor)
    VALUES ('ISO', 'CONDUCE_FORMATO', 'Formulario Conduce Control Puerta', 'FE-GC-02|03');
    PRINT 'Configuración ISO insertada en tabla Defaults';
END;
GO


-- =============================================================================
-- 3. PROCEDIMIENTOS ALMACENADOS
-- =============================================================================

-- 3.1 Búsqueda de Transportista por Placa
CREATE OR ALTER PROCEDURE prtBuscarTransportistaPorPlaca
    @Placa VARCHAR(20)
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        t.idTransportista,
        t.Transportista,
        t.Telefono,
        t.Status,
        e.idTransportistaEquipo,
        e.PlacaNo,
        e.PlacaVence,
        e.TransportistaEquipo,
        e.Capacidad,
        e.idUnidad
    FROM lgTransportista t
    INNER JOIN lgTransportistaEquipo e ON e.idTransportista = t.idTransportista
    WHERE e.PlacaNo = @Placa
      AND t.Status = 'ACTIVO';
END;
GO

-- 3.2 Listar Choferes por Transportista
CREATE OR ALTER PROCEDURE prtListarChoferesPorTransportista
    @idTransportista VARCHAR(16)
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        idTransportistaChofer,
        TransportistaChofer AS NombreChofer,
        LicenciaNo,
        Celular,
        Status
    FROM lgTransportistaChofer
    WHERE idTransportista = @idTransportista
      AND Status = 'ACTIVO';
END;
GO

-- 3.3 Generar Siguiente Secuencia por Almacén
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

    SET @SecuenciaGenerada = @idAlmacen + '-' + RIGHT('00000' + CAST(@NextSeq AS VARCHAR(10)), 5);
END;
GO

-- 3.4 Generar Movimiento de Entrada en Inventario (promov / promovdet)
CREATE OR ALTER PROCEDURE dbo.prtGenerarMovimientoEntrada
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

-- 3.5 Cierre de Día (con integración idéntica a SADE ERP ocRecepcion / ocRecepcionDet)
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

            -- 7. Vincular promov con formato unificado: "Entrada por Conduce: {Conduce} - O/C: {OrdenNumero} (REC:#{RecepcionSeq})"
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

-- 3.6 Consulta de Recepciones con Filtros y Paginación
CREATE OR ALTER PROCEDURE prtConsultarRecepciones
    @FechaDesde     DATETIME        = NULL,
    @FechaHasta     DATETIME        = NULL,
    @Conduce        NVARCHAR(50)    = NULL,
    @Placa          NVARCHAR(20)    = NULL,
    @Transportista  NVARCHAR(200)   = NULL,
    @Status         VARCHAR(20)     = NULL,
    @PageNumber     INT             = 1,
    @PageSize       INT             = 50
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        e.idEntradaCamion,
        e.Conduce,
        e.ConduceTransporte,
        e.Placa,
        e.Transportista,
        e.NombreChofer,
        e.FechaEntrada,
        e.FechaRecepcion,
        e.UsuarioRecepcion,
        e.idProducto,
        e.Producto,
        e.CantidadRecibida,
        e.idUnidad,
        e.idUnidadAlmacen,
        e.CantidadAlmacen,
        e.idSuplidor,
        e.Suplidor,
        e.ProMov,
        e.Status,
        e.idOrden,
        e.OrdenNumero,
        e.idEvidencia,
        e.Notas,
        e.Usuario,
        e.idPuerta,
        e.idTransportista,
        e.idChofer,
        e.idAlmacen,
        COUNT(*) OVER() AS TotalRegistros
    FROM prtEntradaCamion e
    WHERE
        (@FechaDesde    IS NULL OR e.FechaEntrada >= @FechaDesde)
        AND (@FechaHasta IS NULL OR e.FechaEntrada <= @FechaHasta)
        AND (@Conduce    IS NULL OR e.Conduce LIKE '%' + @Conduce + '%')
        AND (@Placa      IS NULL OR e.Placa LIKE '%' + @Placa + '%')
        AND (@Transportista IS NULL OR e.Transportista LIKE '%' + @Transportista + '%')
        AND (@Status     IS NULL OR e.Status = @Status)
    ORDER BY e.FechaEntrada DESC
    OFFSET (@PageNumber - 1) * @PageSize ROWS
    FETCH NEXT @PageSize ROWS ONLY;
END;
GO

PRINT '=============================================================================';
PRINT ' INSTALACIÓN COMPLETA EN BASE DE DATOS ERP FINALIZADA CON ÉXITO ';
PRINT '=============================================================================';
