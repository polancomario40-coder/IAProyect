-- =============================================================================
-- SCRIPT: CREACIÓN DE COMODINES GENÉRICOS Y REGISTRO DE CHOFERES FALTANTES
-- Base de datos: ERP (cbsvmotest / Producción)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. CREAR TRANSPORTISTA GENÉRICO
-- -----------------------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM lgTransportista WHERE idTransportista = 'GENERICO')
BEGIN
    INSERT INTO lgTransportista (
        idTransportista, Transportista, Interno, Telefono, Direccion, Status
    )
    VALUES (
        'GENERICO', 'TRANSPORTISTA GENERICO', 0, '809-000-0000', 'DOMINICANA', 'ACTIVO'
    );
    PRINT 'Transportista GENERICO creado con éxito.';
END
ELSE
BEGIN
    PRINT 'Transportista GENERICO ya existe.';
END;
GO

-- -----------------------------------------------------------------------------
-- 2. CREAR PLACAS GENÉRICAS ('GENERICA' y 'S/P')
-- Para usarse cuando un camión no esté registrado y no detener la operación
-- -----------------------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM lgTransportistaEquipo WHERE UPPER(LTRIM(RTRIM(PlacaNo))) = 'GENERICA')
BEGIN
    INSERT INTO lgTransportistaEquipo (
        idTransportistaEquipo, TransportistaEquipo, idTransportista,
        PlacaNo, PlacaVence, Status, Capacidad, idUnidad
    )
    VALUES (
        NEWID(), 'EQUIPO / PLACA GENERICA', 'GENERICO',
        'GENERICA', '2099-12-31', 'ACTIVO', 0.00, 'M3'
    );
    PRINT 'Placa GENERICA creada.';
END;

IF NOT EXISTS (SELECT 1 FROM lgTransportistaEquipo WHERE UPPER(LTRIM(RTRIM(PlacaNo))) = 'S/P')
BEGIN
    INSERT INTO lgTransportistaEquipo (
        idTransportistaEquipo, TransportistaEquipo, idTransportista,
        PlacaNo, PlacaVence, Status, Capacidad, idUnidad
    )
    VALUES (
        NEWID(), 'EQUIPO SIN PLACA', 'GENERICO',
        'S/P', '2099-12-31', 'ACTIVO', 0.00, 'M3'
    );
    PRINT 'Placa S/P (Sin Placa) creada.';
END;
GO

-- -----------------------------------------------------------------------------
-- 3. CREAR CHOFER GENÉRICO
-- -----------------------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM lgTransportistaChofer WHERE idTransportista = 'GENERICO' AND TransportistaChofer = 'CHOFER GENERICO')
BEGIN
    INSERT INTO lgTransportistaChofer (
        idTransportistaChofer, idTransportista, TransportistaChofer,
        LicenciaNo, LicenciaVence, Status, Celular, Nota
    )
    VALUES (
        NEWID(), 'GENERICO', 'CHOFER GENERICO',
        '000-0000000-0', '2099-12-31', 'ACTIVO', NULL, 'Comodín para choferes no registrados'
    );
    PRINT 'Chofer CHOFER GENERICO creado.';
END;
GO

-- -----------------------------------------------------------------------------
-- 4. ACTUALIZAR PROCEDIMIENTO prtListarChoferesPorTransportista
-- Garantiza que el CHOFER GENERICO (y cualquier chofer del transportista genérico)
-- esté SIEMPRE visible en la lista desplegable de CUALQUIER transportista.
-- -----------------------------------------------------------------------------
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
    WHERE (idTransportista = @idTransportista OR idTransportista = 'GENERICO')
      AND Status = 'ACTIVO'
    ORDER BY 
        CASE WHEN idTransportista = 'GENERICO' THEN 1 ELSE 0 END, 
        TransportistaChofer;
END;
GO
PRINT 'Procedimiento prtListarChoferesPorTransportista actualizado.';
GO

-- -----------------------------------------------------------------------------
-- 5. REGISTRAR EN 'GENERICO' TODOS LOS CHOFERES DEL EXCEL QUE FALTARON
-- Lee la tabla dbo.tmpCargaChoferesPlacas e inserta cualquier chofer que no
-- haya quedado registrado bajo ningún transportista, asignándolo a 'GENERICO'.
-- -----------------------------------------------------------------------------
IF OBJECT_ID('dbo.tmpCargaChoferesPlacas', 'U') IS NOT NULL
BEGIN
    INSERT INTO lgTransportistaChofer (
        idTransportistaChofer,
        idTransportista,
        TransportistaChofer,
        LicenciaNo,
        LicenciaVence,
        Status,
        Celular,
        Nota
    )
    SELECT 
        NEWID(),
        'GENERICO',
        t.NombreLimpio,
        NULLIF(t.CedulaLimpia, ''),
        '2035-12-31',
        'ACTIVO',
        NULL,
        'Cargado desde Excel a Transportista Genérico'
    FROM (
        SELECT DISTINCT
            UPPER(LTRIM(RTRIM(NOMBRE))) AS NombreLimpio,
            LTRIM(RTRIM(REPLACE(REPLACE(CEDULA, '-', ''), ' ', ''))) AS CedulaLimpia
        FROM dbo.tmpCargaChoferesPlacas
        WHERE NOMBRE IS NOT NULL AND LTRIM(RTRIM(NOMBRE)) <> ''
    ) t
    WHERE NOT EXISTS (
        SELECT 1 FROM lgTransportistaChofer c
        WHERE (
            (NULLIF(t.CedulaLimpia, '') IS NOT NULL AND REPLACE(REPLACE(ISNULL(c.LicenciaNo, ''), '-', ''), ' ', '') = t.CedulaLimpia)
            OR UPPER(LTRIM(RTRIM(c.TransportistaChofer))) = t.NombreLimpio
        )
    );

    PRINT 'Choferes faltantes insertados bajo el transportista GENERICO.';
END
ELSE
BEGIN
    PRINT 'Nota: La tabla dbo.tmpCargaChoferesPlacas no existe en este momento. Si necesitas cargar choferes desde Excel, créala primero con el script de carga.';
END;
GO

-- -----------------------------------------------------------------------------
-- CONSULTA DE VERIFICACIÓN
-- -----------------------------------------------------------------------------
SELECT 'Equipos / Placas Genéricas' AS Categoria, PlacaNo, TransportistaEquipo, Status 
FROM lgTransportistaEquipo WHERE idTransportista = 'GENERICO';

SELECT 'Choferes bajo Transportista Genérico' AS Categoria, TransportistaChofer, LicenciaNo, Status 
FROM lgTransportistaChofer WHERE idTransportista = 'GENERICO';
GO
