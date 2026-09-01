-- ============================================================
-- Script: 01_schema_erp_AdelH.sql (v2 - orden de creación corregido)
-- Base de Datos: AdelH (ERP SADE - Transporte Almanzar)
-- ============================================================

USE AdelH;
GO

-- ============================================================
-- 1. prtCierreDia (primero — es referenciada por prtEntradaCamion)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'prtCierreDia')
BEGIN
    CREATE TABLE prtCierreDia (
        idCierre            UNIQUEIDENTIFIER    NOT NULL CONSTRAINT PK_prtCierreDia PRIMARY KEY DEFAULT NEWID(),
        FechaDia            DATE                NOT NULL,
        FechaHoraCierre     DATETIME2(0)        NOT NULL DEFAULT GETDATE(),
        UsuarioCierre       NVARCHAR(50)        NOT NULL,
        TotalRecepciones    INT                 NOT NULL DEFAULT 0,
        TotalConOC          INT                 NOT NULL DEFAULT 0,
        TotalSinOC          INT                 NOT NULL DEFAULT 0,
        Notas               NVARCHAR(500)       NULL,
        CONSTRAINT UQ_prtCierreDia_FechaDia UNIQUE (FechaDia)
    );
    PRINT 'Tabla prtCierreDia creada correctamente.';
END
ELSE
    PRINT 'Tabla prtCierreDia ya existe.';
GO

-- ============================================================
-- 2. prtEntradaCamion (referencia prtCierreDia, lgTransportista, etc.)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'prtEntradaCamion')
BEGIN
    CREATE TABLE prtEntradaCamion (
        idEntradaCamion     UNIQUEIDENTIFIER    NOT NULL CONSTRAINT PK_prtEntradaCamion PRIMARY KEY DEFAULT NEWID(),

        -- Conduce
        Conduce             NVARCHAR(50)        NOT NULL,
        FechaEntrada        DATETIME2(0)        NOT NULL DEFAULT GETDATE(),

        -- Transportista (referencias a tablas existentes de AdelH)
        idTransportista     VARCHAR(16)         NULL CONSTRAINT FK_prtEntradaCamion_Transportista
                                                    REFERENCES lgTransportista(idTransportista),
        Transportista       NVARCHAR(200)       NULL,
        Placa               NVARCHAR(20)        NOT NULL,
        PlacaOcrTexto       NVARCHAR(50)        NULL,
        PlacaOcrConfianza   DECIMAL(5,4)        NULL,

        -- Chofer
        idChofer            UNIQUEIDENTIFIER    NULL CONSTRAINT FK_prtEntradaCamion_Chofer
                                                    REFERENCES lgTransportistaChofer(idTransportistaChofer),
        NombreChofer        NVARCHAR(100)       NULL,

        -- Recepción
        FechaRecepcion      DATETIME2(0)        NULL,
        UsuarioRecepcion    NVARCHAR(50)        NULL,
        idAlmacen           VARCHAR(20)         NULL,

        -- Producto (resumen; detalle en prtEntradaDetalle)
        idProducto          VARCHAR(25)         NULL,
        Producto            NVARCHAR(200)       NULL,

        -- Orden de Compra (asignada en Cierre del Día)
        idOrden             UNIQUEIDENTIFIER    NULL CONSTRAINT FK_prtEntradaCamion_Orden
                                                    REFERENCES ocOrdenes(idOrden),
        OrdenNumero         INT                 NULL,

        -- Evidencias (GUID de enlace cross-BD con SADE_Evidencias)
        idEvidencia         UNIQUEIDENTIFIER    NULL,

        -- Control
        idPuerta            VARCHAR(16)         NULL,
        Notas               NVARCHAR(500)       NULL,
        Status              VARCHAR(20)         NOT NULL DEFAULT 'PENDIENTE',
        --  PENDIENTE  → En puerta, sin recibir por almacenista
        --  RECIBIDO   → Almacenista confirmó
        --  CERRADO    → Cierre con OC asignada
        --  BLOQUEADO  → Cierre SIN OC → no puede ir a CxP

        -- Auditoría
        Usuario             NVARCHAR(50)        NOT NULL,
        FechaCreacion       DATETIME2(0)        NOT NULL DEFAULT GETDATE(),
        FechaModificacion   DATETIME2(0)        NULL,
        UsuarioModificacion NVARCHAR(50)        NULL,

        -- Vínculo con cierre
        idCierre            UNIQUEIDENTIFIER    NULL CONSTRAINT FK_prtEntradaCamion_Cierre
                                                    REFERENCES prtCierreDia(idCierre),
        FechaCierre         DATETIME2(0)        NULL,
        UsuarioCierre       NVARCHAR(50)        NULL
    );

    CREATE INDEX IX_prtEntradaCamion_Conduce      ON prtEntradaCamion (Conduce);
    CREATE INDEX IX_prtEntradaCamion_Placa         ON prtEntradaCamion (Placa);
    CREATE INDEX IX_prtEntradaCamion_FechaEntrada  ON prtEntradaCamion (FechaEntrada);
    CREATE INDEX IX_prtEntradaCamion_Status        ON prtEntradaCamion (Status);
    CREATE INDEX IX_prtEntradaCamion_Transportista ON prtEntradaCamion (idTransportista);

    PRINT 'Tabla prtEntradaCamion creada correctamente.';
END
ELSE
    PRINT 'Tabla prtEntradaCamion ya existe.';
GO

-- ============================================================
-- 3. prtEntradaDetalle
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'prtEntradaDetalle')
BEGIN
    CREATE TABLE prtEntradaDetalle (
        idEntradaDetalle    UNIQUEIDENTIFIER    NOT NULL CONSTRAINT PK_prtEntradaDetalle PRIMARY KEY DEFAULT NEWID(),
        idEntradaCamion     UNIQUEIDENTIFIER    NOT NULL CONSTRAINT FK_prtEntradaDetalle_Entrada
                                                    REFERENCES prtEntradaCamion(idEntradaCamion) ON DELETE CASCADE,
        idProducto          VARCHAR(25)         NULL,
        Producto            NVARCHAR(200)       NULL,
        Cantidad            DECIMAL(18,4)       NULL,
        idUnidad            VARCHAR(16)         NULL,
        Notas               NVARCHAR(300)       NULL,
        Orden               INT                 NOT NULL DEFAULT 1
    );

    CREATE INDEX IX_prtEntradaDetalle_Entrada ON prtEntradaDetalle (idEntradaCamion);

    PRINT 'Tabla prtEntradaDetalle creada correctamente.';
END
ELSE
    PRINT 'Tabla prtEntradaDetalle ya existe.';
GO

-- ============================================================
-- 4. Stored Procedures
-- ============================================================

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

CREATE OR ALTER PROCEDURE prtRegistrarEntrada
    @idEntradaCamion    UNIQUEIDENTIFIER,
    @Conduce            NVARCHAR(50),
    @Placa              NVARCHAR(20),
    @PlacaOcrTexto      NVARCHAR(50),
    @PlacaOcrConfianza  DECIMAL(5,4),
    @idTransportista    VARCHAR(16),
    @Transportista      NVARCHAR(200),
    @idChofer           UNIQUEIDENTIFIER,
    @NombreChofer       NVARCHAR(100),
    @idProducto         VARCHAR(25),
    @Producto           NVARCHAR(200),
    @idAlmacen          VARCHAR(20),
    @idPuerta           VARCHAR(16),
    @Notas              NVARCHAR(500),
    @Usuario            NVARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        INSERT INTO prtEntradaCamion (
            idEntradaCamion, Conduce, Placa, PlacaOcrTexto, PlacaOcrConfianza,
            idTransportista, Transportista, idChofer, NombreChofer,
            idProducto, Producto, idAlmacen, idPuerta, Notas, Usuario, Status
        ) VALUES (
            @idEntradaCamion, @Conduce, @Placa, @PlacaOcrTexto, @PlacaOcrConfianza,
            @idTransportista, @Transportista, @idChofer, @NombreChofer,
            @idProducto, @Producto, @idAlmacen, @idPuerta, @Notas, @Usuario, 'PENDIENTE'
        );
        SELECT 'OK' AS Resultado, @idEntradaCamion AS idEntradaCamion;
    END TRY
    BEGIN CATCH
        THROW;
    END CATCH;
END;
GO

CREATE OR ALTER PROCEDURE prtConfirmarRecepcion
    @idEntradaCamion    UNIQUEIDENTIFIER,
    @FechaRecepcion     DATETIME2(0),
    @UsuarioRecepcion   NVARCHAR(50),
    @idEvidencia        UNIQUEIDENTIFIER,
    @Notas              NVARCHAR(500)
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE prtEntradaCamion SET
        FechaRecepcion      = @FechaRecepcion,
        UsuarioRecepcion    = @UsuarioRecepcion,
        idEvidencia         = @idEvidencia,
        Notas               = ISNULL(@Notas, Notas),
        Status              = 'RECIBIDO',
        FechaModificacion   = GETDATE(),
        UsuarioModificacion = @UsuarioRecepcion
    WHERE idEntradaCamion = @idEntradaCamion;

    SELECT @@ROWCOUNT AS FilasAfectadas;
END;
GO

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
        e.Placa,
        e.Transportista,
        e.NombreChofer,
        e.FechaEntrada,
        e.FechaRecepcion,
        e.UsuarioRecepcion,
        e.idProducto,
        e.Producto,
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

CREATE OR ALTER PROCEDURE prtObtenerPendientesCierre
    @FechaDia DATETIME = NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF @FechaDia IS NULL SET @FechaDia = CAST(GETDATE() AS DATE);

    SELECT
        e.idEntradaCamion,
        e.Conduce,
        e.Placa,
        e.Transportista,
        e.NombreChofer,
        e.FechaEntrada,
        e.FechaRecepcion,
        e.idProducto,
        e.Producto,
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
        0 AS TotalRegistros
    FROM prtEntradaCamion e
    WHERE CAST(e.FechaEntrada AS DATE) = CAST(@FechaDia AS DATE)
      AND e.Status IN ('PENDIENTE', 'RECIBIDO')
    ORDER BY e.FechaEntrada;
END;
GO

CREATE OR ALTER PROCEDURE prtEjecutarCierreDia
    @FechaDia       DATETIME,
    @UsuarioCierre  NVARCHAR(50),
    @Notas          NVARCHAR(500) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;

        DECLARE @idCierre UNIQUEIDENTIFIER = NEWID();
        DECLARE @totalRec INT, @totalConOC INT, @totalSinOC INT;

        SELECT
            @totalRec   = COUNT(*),
            @totalConOC = SUM(CASE WHEN idOrden IS NOT NULL THEN 1 ELSE 0 END),
            @totalSinOC = SUM(CASE WHEN idOrden IS NULL     THEN 1 ELSE 0 END)
        FROM prtEntradaCamion
        WHERE CAST(FechaEntrada AS DATE) = CAST(@FechaDia AS DATE)
          AND Status IN ('PENDIENTE', 'RECIBIDO');

        INSERT INTO prtCierreDia (idCierre, FechaDia, UsuarioCierre, TotalRecepciones, TotalConOC, TotalSinOC, Notas)
        VALUES (@idCierre, CAST(@FechaDia AS DATE), @UsuarioCierre, ISNULL(@totalRec,0), ISNULL(@totalConOC,0), ISNULL(@totalSinOC,0), @Notas);

        UPDATE prtEntradaCamion SET
            Status = 'CERRADO', idCierre = @idCierre,
            FechaCierre = GETDATE(), UsuarioCierre = @UsuarioCierre
        WHERE CAST(FechaEntrada AS DATE) = CAST(@FechaDia AS DATE)
          AND Status IN ('PENDIENTE','RECIBIDO') AND idOrden IS NOT NULL;

        UPDATE prtEntradaCamion SET
            Status = 'BLOQUEADO', idCierre = @idCierre,
            FechaCierre = GETDATE(), UsuarioCierre = @UsuarioCierre
        WHERE CAST(FechaEntrada AS DATE) = CAST(@FechaDia AS DATE)
          AND Status IN ('PENDIENTE','RECIBIDO') AND idOrden IS NULL;

        COMMIT TRANSACTION;

        SELECT @idCierre AS idCierre, ISNULL(@totalRec,0) AS TotalRecepciones,
               ISNULL(@totalConOC,0) AS TotalConOC, ISNULL(@totalSinOC,0) AS TotalSinOC;
    END TRY
    BEGIN CATCH
        ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
GO

PRINT '=== Scripts de Control de Puerta aplicados en AdelH ===';
