-- =============================================================================
-- SCRIPT: ELIMINACIÓN DE TRANSPORTISTAS, PLACAS Y CHOFERES GENÉRICOS
-- Y ACTUALIZACIÓN DE REPORTES PARA INCLUIR PLANTA / ALMACÉN
-- Base de datos: ERP CBSVMO
-- =============================================================================

-- 1. ELIMINAR CHOFERES GENÉRICOS
DELETE FROM lgTransportistaChofer 
WHERE idTransportista = 'GENERICO' 
   OR TransportistaChofer = 'CHOFER GENERICO'
   OR TransportistaChofer LIKE '%GENERIC%';
PRINT 'Choferes genéricos eliminados.';

-- 2. ELIMINAR EQUIPOS / PLACAS GENÉRICAS
DELETE FROM lgTransportistaEquipo 
WHERE idTransportista = 'GENERICO' 
   OR UPPER(LTRIM(RTRIM(PlacaNo))) IN ('GENERICA', 'S/P', 'SIN PLACA')
   OR TransportistaEquipo LIKE '%GENERIC%'
   OR TransportistaEquipo LIKE '%SIN PLACA%';
PRINT 'Placas y equipos genéricos eliminados.';

-- 3. ELIMINAR TRANSPORTISTAS GENÉRICOS
DELETE FROM lgTransportista 
WHERE idTransportista = 'GENERICO' 
   OR Transportista = 'TRANSPORTISTA GENERICO'
   OR Transportista LIKE '%GENERIC%';
PRINT 'Transportistas genéricos eliminados.';

-- 4. ELIMINAR TABLA prtChoferesGenericos SI EXISTE
IF OBJECT_ID('dbo.prtChoferesGenericos', 'U') IS NOT NULL
BEGIN
    DROP TABLE dbo.prtChoferesGenericos;
    PRINT 'Tabla prtChoferesGenericos eliminada.';
END;
GO

-- 5. ACTUALIZAR PROCEDIMIENTO prtListarChoferesPorTransportista
-- Ahora SOLO lista los choferes reales que pertenecen al transportista seleccionado
CREATE OR ALTER PROC prtListarChoferesPorTransportista
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
      AND Status = 'ACTIVO'
      AND TransportistaChofer NOT LIKE '%GENERIC%'
    ORDER BY TransportistaChofer;
END;
GO
PRINT 'Procedimiento prtListarChoferesPorTransportista actualizado.';
GO

-- 6. ACTUALIZAR PROCEDIMIENTO prtBuscarTransportistaPorPlaca
-- Blindado para no permitir comodines ni placas genéricas
CREATE OR ALTER PROC prtBuscarTransportistaPorPlaca
    @Placa VARCHAR(20)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @PlacaLimpia VARCHAR(20) = UPPER(LTRIM(RTRIM(@Placa)));

    IF @PlacaLimpia IN ('GENERICA', 'S/P', 'SIN PLACA') OR @PlacaLimpia LIKE '%GENERIC%'
    BEGIN
        RETURN;
    END;

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
    WHERE UPPER(LTRIM(RTRIM(e.PlacaNo))) = @PlacaLimpia
      AND t.Status = 'ACTIVO'
      AND e.Status = 'ACTIVO'
      AND t.idTransportista <> 'GENERICO'
      AND t.Transportista NOT LIKE '%GENERIC%';
END;
GO
PRINT 'Procedimiento prtBuscarTransportistaPorPlaca actualizado.';
GO

-- 7. ACTUALIZAR PROCEDIMIENTO prtConsultarRecepciones
-- Incluye campo Almacen (Planta) y filtro por @idAlmacen
CREATE OR ALTER PROCEDURE [dbo].[prtConsultarRecepciones]
    @FechaDesde     DATETIME        = NULL,
    @FechaHasta     DATETIME        = NULL,
    @Conduce        NVARCHAR(50)    = NULL,
    @Placa          NVARCHAR(20)    = NULL,
    @Transportista  NVARCHAR(200)   = NULL,
    @Status         VARCHAR(20)     = NULL,
    @idAlmacen      VARCHAR(20)     = NULL,
    @PageNumber     INT             = 1,
    @PageSize       INT             = 50,
    @UsuarioPermiso NVARCHAR(50)    = NULL
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
        ISNULL(a.Almacen, ISNULL(e.idAlmacen, '-')) AS Almacen,
        oc.Recepcion AS NumRecepcionOC,
        COUNT(*) OVER() AS TotalRegistros
    FROM prtEntradaCamion e
    LEFT JOIN ocRecepcion oc ON e.ProMov = oc.Referencia AND oc.TipoReferencia = 'PRT'
    LEFT JOIN Almacen a ON a.idAlmacen = e.idAlmacen
    WHERE
        (@FechaDesde    IS NULL OR e.FechaEntrada >= @FechaDesde)
        AND (@FechaHasta IS NULL OR e.FechaEntrada <= DATEADD(SECOND, 86399, CAST(CAST(@FechaHasta AS DATE) AS DATETIME)))
        AND (@Conduce    IS NULL OR e.Conduce LIKE '%' + @Conduce + '%')
        AND (@Placa      IS NULL OR e.Placa LIKE '%' + @Placa + '%')
        AND (@Transportista IS NULL OR e.Transportista LIKE '%' + @Transportista + '%')
        AND (@Status     IS NULL OR e.Status = @Status)
        AND (@idAlmacen  IS NULL OR e.idAlmacen = @idAlmacen)
        AND (@UsuarioPermiso IS NULL OR e.idAlmacen IS NULL 
             OR e.idAlmacen IN (SELECT idAlmacen FROM AlmacenPermiso WHERE idSegUserGrp = @UsuarioPermiso))
    ORDER BY e.FechaEntrada DESC
    OFFSET (@PageNumber - 1) * @PageSize ROWS
    FETCH NEXT @PageSize ROWS ONLY;
END;
GO
PRINT 'Procedimiento prtConsultarRecepciones actualizado con campo y filtro de Planta.';
GO
