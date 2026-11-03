-- =============================================================================
-- SCRIPT: TABLAS Y PROCEDIMIENTOS PARA EL MÓDULO DE CONCILIACIÓN DE SUPLIDORES
-- Y FLUJO DE CUENTAS POR PAGAR (CXP)
-- Base de datos: ERP CBSVMO
-- =============================================================================

-- 1. TABLA CABECERA: prtConciliacionLote
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'prtConciliacionLote')
BEGIN
    CREATE TABLE prtConciliacionLote (
        idConciliacion          UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        NumeroConciliacion      VARCHAR(30)      NOT NULL,
        idSuplidor              VARCHAR(15)      NULL,
        Suplidor                VARCHAR(200)     NOT NULL,
        FechaCarga              DATETIME         NOT NULL DEFAULT GETDATE(),
        Usuario                 VARCHAR(100)     NOT NULL,
        NombreArchivo           VARCHAR(250)     NULL,
        TotalConduces           INT              NOT NULL DEFAULT 0,
        TotalCalifican          INT              NOT NULL DEFAULT 0,
        TotalRechazados         INT              NOT NULL DEFAULT 0,
        TotalPendientes         INT              NOT NULL DEFAULT 0,
        MontoTotalReclamado     DECIMAL(18,2)    NOT NULL DEFAULT 0.00,
        MontoTotalCalifica      DECIMAL(18,2)    NOT NULL DEFAULT 0.00,
        Status                  VARCHAR(30)      NOT NULL DEFAULT 'REVISADO', -- 'REVISADO', 'APROBADO_PAGO', 'EN_CXP', 'PAGADO', 'ANULADO'
        FechaAprobacion         DATETIME         NULL,
        UsuarioAprobacion       VARCHAR(100)     NULL,
        Notas                   VARCHAR(500)     NULL,
        FechaCreacion           DATETIME         NOT NULL DEFAULT GETDATE()
    );
    PRINT 'Tabla prtConciliacionLote creada con éxito.';
END;
GO

-- 2. TABLA DETALLE: prtConciliacionDetalle
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'prtConciliacionDetalle')
BEGIN
    CREATE TABLE prtConciliacionDetalle (
        idDetalle               UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        idConciliacion          UNIQUEIDENTIFIER NOT NULL CONSTRAINT FK_prtConciliacionDetalle_Lote REFERENCES prtConciliacionLote(idConciliacion) ON DELETE CASCADE,
        -- Datos declarados por el Suplidor en Plantilla Excel
        FechaConduce            DATETIME         NULL,
        NoConduce               VARCHAR(50)      NOT NULL,
        Producto                VARCHAR(200)     NULL,
        Mina                    VARCHAR(100)     NULL,
        Planta                  VARCHAR(100)     NULL,
        CantidadDeclarada       DECIMAL(18,4)    NOT NULL DEFAULT 0.0000,
        PrecioUnitario          DECIMAL(18,4)    NOT NULL DEFAULT 0.0000,
        TotalReclamado          DECIMAL(18,2)    NOT NULL DEFAULT 0.00,
        -- Datos encontrados y conciliados con nuestro Sistema (Control Puerta / ERP)
        idEntradaCamion         UNIQUEIDENTIFIER NULL,
        ProMov                  VARCHAR(20)      NULL,
        NumRecepcionOC          VARCHAR(50)      NULL,
        OrdenNumero             INT              NULL,
        idOrden                 UNIQUEIDENTIFIER NULL,
        ProductoEncontrado      VARCHAR(200)     NULL,
        PlantaEncontrada        VARCHAR(100)     NULL,
        CantidadSistema         DECIMAL(18,4)    NULL,
        UnidadSistema           VARCHAR(20)      NULL,
        PrecioSistema           DECIMAL(18,4)    NULL,
        TotalAprobado           DECIMAL(18,2)    NULL,
        -- Resultado del Análisis de Cuadre
        EstadoCuadre            VARCHAR(30)      NOT NULL, -- 'CALIFICA_PAGO', 'NO_CALIFICA', 'PENDIENTE_RECEPCION'
        MotivoRechazo           VARCHAR(500)     NULL,
        -- Flujo de Pago hacia Cuentas por Pagar (CXP)
        EstadoPago              VARCHAR(30)      NOT NULL DEFAULT 'PENDIENTE', -- 'PENDIENTE', 'CALIFICA_PAGO', 'RECHAZADO', 'APROBADO', 'PAGADO'
        FechaPago               DATETIME         NULL,
        ReferenciaPago          VARCHAR(100)     NULL,
        Notas                   VARCHAR(500)     NULL,
        FechaCreacion           DATETIME         NOT NULL DEFAULT GETDATE()
    );
    CREATE INDEX IX_prtConciliacionDetalle_Conduce ON prtConciliacionDetalle(NoConduce);
    CREATE INDEX IX_prtConciliacionDetalle_Lote ON prtConciliacionDetalle(idConciliacion);
    PRINT 'Tabla prtConciliacionDetalle creada con éxito.';
END;
GO

-- 3. PROCEDIMIENTO PARA LISTAR HISTORIAL DE LOTES DE CONCILIACIÓN
CREATE OR ALTER PROCEDURE prtListarLotesConciliacion
    @idSuplidor VARCHAR(15) = NULL,
    @Status VARCHAR(30) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SELECT 
        l.idConciliacion,
        l.NumeroConciliacion,
        l.idSuplidor,
        l.Suplidor,
        l.FechaCarga,
        l.Usuario,
        l.NombreArchivo,
        l.TotalConduces,
        l.TotalCalifican,
        l.TotalRechazados,
        l.TotalPendientes,
        l.MontoTotalReclamado,
        l.MontoTotalCalifica,
        l.Status,
        l.FechaAprobacion,
        l.UsuarioAprobacion,
        l.Notas
    FROM prtConciliacionLote l
    WHERE (@idSuplidor IS NULL OR l.idSuplidor = @idSuplidor)
      AND (@Status IS NULL OR l.Status = @Status)
    ORDER BY l.FechaCarga DESC;
END;
GO
PRINT 'Procedimiento prtListarLotesConciliacion creado.';
GO

-- 4. PROCEDIMIENTO PARA OBTENER EL DETALLE DE UN LOTE
CREATE OR ALTER PROCEDURE prtObtenerDetalleConciliacion
    @idConciliacion UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        d.idDetalle,
        d.idConciliacion,
        d.FechaConduce,
        d.NoConduce,
        d.Producto,
        d.Mina,
        d.Planta,
        d.CantidadDeclarada,
        d.PrecioUnitario,
        d.TotalReclamado,
        d.idEntradaCamion,
        d.ProMov,
        d.NumRecepcionOC,
        d.OrdenNumero,
        d.idOrden,
        d.ProductoEncontrado,
        d.PlantaEncontrada,
        d.CantidadSistema,
        d.UnidadSistema,
        d.PrecioSistema,
        d.TotalAprobado,
        d.EstadoCuadre,
        d.MotivoRechazo,
        d.EstadoPago,
        d.FechaPago,
        d.ReferenciaPago,
        d.Notas
    FROM prtConciliacionDetalle d
    WHERE d.idConciliacion = @idConciliacion
    ORDER BY 
        CASE d.EstadoCuadre 
            WHEN 'CALIFICA_PAGO' THEN 1 
            WHEN 'PENDIENTE_RECEPCION' THEN 2 
            ELSE 3 
        END,
        d.NoConduce;
END;
GO
PRINT 'Procedimiento prtObtenerDetalleConciliacion creado.';
GO
