-- =============================================================================
-- SCRIPT: CARGA MASIVA DE CHOFERES Y PLACAS DESDE EXCEL
-- Base de datos: ERP (cbsvmotest / Producción)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- PASO 1: CREAR TABLA DE PASO (Solo se crea si NO existe, NO borra los datos)
-- -----------------------------------------------------------------------------
--IF OBJECT_ID('dbo.tmpCargaChoferesPlacas', 'U') IS NULL
--BEGIN
--    CREATE TABLE dbo.tmpCargaChoferesPlacas (
--        NOMBRE       VARCHAR(150)  NULL,
--        CEDULA       VARCHAR(50)   NULL,
--        VOLQUETA     VARCHAR(50)   NULL,
--        CABEZOTE     VARCHAR(50)   NULL,
--        MEDIDA       DECIMAL(18,4) NULL
--    );
--    PRINT 'Tabla dbo.tmpCargaChoferesPlacas creada exitosamente.';
--END
--ELSE
--BEGIN
--    PRINT 'Tabla dbo.tmpCargaChoferesPlacas ya existía (conserva tus datos).';
--END;
--GO

-- -----------------------------------------------------------------------------
-- PASO 2: VALIDACIÓN Y PROCESAMIENTO
-- -----------------------------------------------------------------------------
DECLARE @TotalEnTabla INT;
SELECT @TotalEnTabla = COUNT(1) FROM dbo.tmpCargaChoferesPlacas;

IF @TotalEnTabla = 0
BEGIN
    RAISERROR('ATENCIÓN: La tabla dbo.tmpCargaChoferesPlacas está VACÍA (0 filas). Pega primero las filas desde Excel antes de ejecutar este paso.', 16, 1);
    RETURN;
END;

-- Definir a qué transportista se asociarán por defecto:
-- Si deseas que pertenezcan a VMO usa '4'.
-- Si deseas que pertenezcan al comodín para que estén disponibles para todos usa 'GENERICO'.
DECLARE @idTransportista VARCHAR(16) = '4';

-- Asegurar que el transportista genérico exista siempre
IF NOT EXISTS (SELECT 1 FROM lgTransportista WHERE idTransportista = 'GENERICO')
BEGIN
    INSERT INTO lgTransportista (idTransportista, Transportista, Interno, Telefono, Direccion, Status)
    VALUES ('GENERICO', 'TRANSPORTISTA GENERICO', 0, '809-000-0000', 'DOMINICANA', 'ACTIVO');
END;

-- Asegurar placa genérica
IF NOT EXISTS (SELECT 1 FROM lgTransportistaEquipo WHERE UPPER(LTRIM(RTRIM(PlacaNo))) = 'GENERICA')
BEGIN
    INSERT INTO lgTransportistaEquipo (idTransportistaEquipo, TransportistaEquipo, idTransportista, PlacaNo, PlacaVence, Status, Capacidad, idUnidad)
    VALUES (NEWID(), 'EQUIPO / PLACA GENERICA', 'GENERICO', 'GENERICA', '2099-12-31', 'ACTIVO', 0.00, 'M3');
END;

-- Asegurar chofer genérico
IF NOT EXISTS (SELECT 1 FROM lgTransportistaChofer WHERE idTransportista = 'GENERICO' AND TransportistaChofer = 'CHOFER GENERICO')
BEGIN
    INSERT INTO lgTransportistaChofer (idTransportistaChofer, idTransportista, TransportistaChofer, LicenciaNo, LicenciaVence, Status, Celular, Nota)
    VALUES (NEWID(), 'GENERICO', 'CHOFER GENERICO', '000-0000000-0', '2099-12-31', 'ACTIVO', NULL, 'Comodín genérico');
END;

BEGIN TRANSACTION;
BEGIN TRY
    -- -------------------------------------------------------------------------
    -- A) INSERTAR TODOS LOS CHOFERES DEL EXCEL
    -- Inserta choferes únicos que tengan nombre
    -- -------------------------------------------------------------------------
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
        @idTransportista,
        t.NombreLimpio,
        NULLIF(t.CedulaLimpia, ''),
        '2035-12-31',
        'ACTIVO',
        NULL,
        'Cargado desde Excel'
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

    -- -------------------------------------------------------------------------
    -- B) INSERTAR VOLQUETAS CON SU MEDIDA
    -- -------------------------------------------------------------------------
    INSERT INTO lgTransportistaEquipo (
        idTransportistaEquipo,
        TransportistaEquipo,
        idTransportista,
        PlacaNo,
        PlacaVence,
        Status,
        Capacidad,
        idUnidad
    )
    SELECT 
        NEWID(),
        'Volqueta ' + t.PlacaLimpia,
        @idTransportista,
        t.PlacaLimpia,
        '2035-12-31',
        'ACTIVO',
        t.MedidaMax,
        'M3'
    FROM (
        SELECT 
            UPPER(LTRIM(RTRIM(VOLQUETA))) AS PlacaLimpia,
            MAX(MEDIDA) AS MedidaMax
        FROM dbo.tmpCargaChoferesPlacas
        WHERE VOLQUETA IS NOT NULL AND LTRIM(RTRIM(VOLQUETA)) <> ''
        GROUP BY UPPER(LTRIM(RTRIM(VOLQUETA)))
    ) t
    WHERE NOT EXISTS (
        SELECT 1 FROM lgTransportistaEquipo e
        WHERE UPPER(LTRIM(RTRIM(e.PlacaNo))) = t.PlacaLimpia
    );

    -- Actualizar capacidad si la placa ya existía pero no tenía medida
    UPDATE e
    SET e.Capacidad = t.MedidaMax
    FROM lgTransportistaEquipo e
    INNER JOIN (
        SELECT 
            UPPER(LTRIM(RTRIM(VOLQUETA))) AS PlacaLimpia,
            MAX(MEDIDA) AS MedidaMax
        FROM dbo.tmpCargaChoferesPlacas
        WHERE VOLQUETA IS NOT NULL AND LTRIM(RTRIM(VOLQUETA)) <> ''
        GROUP BY UPPER(LTRIM(RTRIM(VOLQUETA)))
    ) t ON UPPER(LTRIM(RTRIM(e.PlacaNo))) = t.PlacaLimpia
    WHERE e.Capacidad IS NULL OR e.Capacidad = 0;

    -- -------------------------------------------------------------------------
    -- C) INSERTAR CABEZOTES (si tienen placa en el Excel)
    -- -------------------------------------------------------------------------
    INSERT INTO lgTransportistaEquipo (
        idTransportistaEquipo,
        TransportistaEquipo,
        idTransportista,
        PlacaNo,
        PlacaVence,
        Status,
        Capacidad,
        idUnidad
    )
    SELECT 
        NEWID(),
        'Cabezote ' + t.PlacaLimpia,
        @idTransportista,
        t.PlacaLimpia,
        '2035-12-31',
        'ACTIVO',
        t.MedidaMax,
        'M3'
    FROM (
        SELECT 
            UPPER(LTRIM(RTRIM(CABEZOTE))) AS PlacaLimpia,
            MAX(MEDIDA) AS MedidaMax
        FROM dbo.tmpCargaChoferesPlacas
        WHERE CABEZOTE IS NOT NULL AND LTRIM(RTRIM(CABEZOTE)) <> ''
        GROUP BY UPPER(LTRIM(RTRIM(CABEZOTE)))
    ) t
    WHERE NOT EXISTS (
        SELECT 1 FROM lgTransportistaEquipo e
        WHERE UPPER(LTRIM(RTRIM(e.PlacaNo))) = t.PlacaLimpia
    );

    COMMIT TRANSACTION;

    PRINT '==================================================';
    PRINT '¡PROCESO COMPLETADO EXITOSAMENTE!';
    PRINT '==================================================';

    -- Resultados
    SELECT 'Filas leídas de la tabla temporal' AS Metrica, COUNT(1) AS Total FROM dbo.tmpCargaChoferesPlacas
    UNION ALL
    SELECT 'Total choferes registrados en el transportista ' + @idTransportista, COUNT(1) FROM lgTransportistaChofer WHERE idTransportista = @idTransportista
    UNION ALL
    SELECT 'Total choferes en GENERICO', COUNT(1) FROM lgTransportistaChofer WHERE idTransportista = 'GENERICO'
    UNION ALL
    SELECT 'Total equipos/placas en el transportista ' + @idTransportista, COUNT(1) FROM lgTransportistaEquipo WHERE idTransportista = @idTransportista;

END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
