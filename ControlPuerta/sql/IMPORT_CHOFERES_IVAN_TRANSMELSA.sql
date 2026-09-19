-- =============================================================================
-- SCRIPT DE IMPORTACIÓN DE TRANSPORTISTAS, EQUIPOS (PLACAS) Y CHOFERES EN CBSVMO
-- =============================================================================
USE CBSVMO;
GO

SET NOCOUNT ON;

BEGIN TRANSACTION;
BEGIN TRY

    -- -------------------------------------------------------------------------
    -- 1. ASEGURAR TRANSPORTISTAS
    -- -------------------------------------------------------------------------
    -- A) TRANSPORTE IVAN
    DECLARE @idTransporteIvan VARCHAR(16);
    SELECT @idTransporteIvan = idTransportista 
    FROM lgTransportista 
    WHERE UPPER(LTRIM(RTRIM(Transportista))) = 'TRANSPORTE IVAN';

    IF @idTransporteIvan IS NULL
    BEGIN
        DECLARE @nextId INT;
        SELECT @nextId = ISNULL(MAX(TRY_CAST(idTransportista AS INT)), 0) + 1 FROM lgTransportista;
        SET @idTransporteIvan = CAST(@nextId AS VARCHAR(16));

        INSERT INTO lgTransportista (idTransportista, Transportista, Interno, Telefono, Direccion, Status)
        VALUES (@idTransporteIvan, 'TRANSPORTE IVAN', 0, '809-000-0000', 'DOMINICANA', 'ACTIVO');

        PRINT 'Transportista TRANSPORTE IVAN creado con ID: ' + @idTransporteIvan;
    END
    ELSE
    BEGIN
        PRINT 'Transportista TRANSPORTE IVAN ya existe con ID: ' + @idTransporteIvan;
    END;

    -- B) TRANSMELSA
    DECLARE @idTransmelsa VARCHAR(16);
    SELECT @idTransmelsa = idTransportista 
    FROM lgTransportista 
    WHERE UPPER(LTRIM(RTRIM(Transportista))) = 'TRANSMELSA';

    IF @idTransmelsa IS NULL
    BEGIN
        DECLARE @nextId2 INT;
        SELECT @nextId2 = ISNULL(MAX(TRY_CAST(idTransportista AS INT)), 0) + 1 FROM lgTransportista;
        SET @idTransmelsa = CAST(@nextId2 AS VARCHAR(16));

        INSERT INTO lgTransportista (idTransportista, Transportista, Interno, Telefono, Direccion, Status)
        VALUES (@idTransmelsa, 'TRANSMELSA', 0, '809-000-0000', 'DOMINICANA', 'ACTIVO');

        PRINT 'Transportista TRANSMELSA creado con ID: ' + @idTransmelsa;
    END
    ELSE
    BEGIN
        PRINT 'Transportista TRANSMELSA ya existe con ID: ' + @idTransmelsa;
    END;

    -- -------------------------------------------------------------------------
    -- 2. TABLA TEMPORAL CON LOS DATOS SUMINISTRADOS
    -- -------------------------------------------------------------------------
    CREATE TABLE #TmpImport (
        Num INT,
        NombreChofer VARCHAR(100),
        Cedula VARCHAR(30),
        Marca VARCHAR(50),
        Placa VARCHAR(20),
        Color VARCHAR(30),
        Transporte VARCHAR(100),
        Producto VARCHAR(50)
    );

    INSERT INTO #TmpImport (Num, NombreChofer, Cedula, Marca, Placa, Color, Transporte, Producto) VALUES
    (1,  'YUNIOR VALLEJO CASILLA',         '402-5919210-8',       'CHAMAN',  'S026342', 'AZUL',   'TRANSPORTE IVAN', 'AGREGADO'),
    (2,  'EDUARDODE JESUS DIAZ',          '084-0016647-9',       'MACK',    'F004029', 'ROJO',   'TRANSPORTE IVAN', 'AGREGADO'),
    (3,  'JOSE LUIS NOVA SANCHEZ',        '002-0102383-5',       'MACK',    'F007535', 'AZUL',   'TRANSPORTE IVAN', 'AGREGADO'),
    (4,  'JAROLRAFAEL SUAREZ',            '402-1884994-7',       'MACK',    'L031819', 'AZUL',   'TRANSPORTE IVAN', 'AGREGADO'),
    (5,  'ANEUDY ALEJANDRO MERCEDES',     '084-0016075-3',       'MACK',    'S009331', 'ROJO',   'TRANSPORTE IVAN', 'AGREGADO'),
    (6,  'CESAR ENRIQUE RIVERA',          '402-5385232-7',       'MACK',    'F005391', 'ROJO',   'TRANSPORTE IVAN', 'AGREGADO'),
    (7,  'PEDRO LUIS RODRIGUEZ',          '402-2298923-4',       'MACK',    'F005871', 'ROJO',   'TRANSPORTE IVAN', 'AGREGADO'),
    (8,  'MARCELIN SMITH',                'PASAPORTE R12271650', 'MACK',    'L121952', 'BLANCO', 'TRANSPORTE IVAN', 'AGREGADO'),
    (9,  'JOSE MANUEL MARTINEZ',          '084-0017567-8',       'TOYOTA',  'L117641', 'BLANCO', 'TRANSPORTE IVAN', 'AGREGADO'),
    (10, 'ANEUDYZ GUZMAN CARMONA',        '225-0033897-9',       'MACK',    'L264504', 'BLANCO', 'TRANSMELSA',       'AGREGADO'),
    (11, 'LUCIANO ANTONIO SORIANO SOTO',  '093-0025493-6',       'MACK',    'L428340', 'BLANCO', 'TRANSMELSA',       'AGREGADO'),
    (12, 'JUAN PABLO CIPRIAN LUCA',       '002-0093730-8',       'KENWOTH', 'L399996', 'ROJO',   'TRANSMELSA',       'AGREGADO'),
    (13, 'CAMILO MARIÑE RIVERA',          '001-1713202-7',       'DAYUN',   'S024920', 'VERDE',  'TRANSMELSA',       'AGREGADO'),
    (14, 'LUIS MANUEL HENRIQUEZ',         '017-0101632-3',       'DAYUN',   'S024921', 'VERDE',  'TRANSMELSA',       'AGREGADO'),
    (15, 'AMERICO CABRERA',               '016-0015939-4',       'DAYUN',   'S024918', 'VERDE',  'TRANSMELSA',       'AGREGADO'),
    (16, 'GERONIMO ALCANTARA',            '082-0015434-5',       'SHACMAN', 'PP622803','BLANCO', 'TRANSMELSA',       'AGREGADO'),
    (17, 'ANTOLIN PEREZ GUTIERRE',        '091-0002914-0',       'SHACMAN', 'PP502690','BLANCO', 'TRANSMELSA',       'AGREGADO'),
    (18, 'ALFREDO FERREIRA HIDALGO',      '002-0083750-8',       'SHACMAN', 'S027380', 'BLANCO', 'TRANSMELSA',       'AGREGADO'),
    (19, 'JOSE VALENTIN SOSA',            '068-0008589-3',       'SHACMAN', 'PP343289','BLANCO', 'TRANSMELSA',       'AGREGADO'),
    (20, 'TAMIS BIENVENIDO MARTINEZ MATEO','001-1297586-7',      'MACK',    'L451938', 'VERDE',  'TRANSMELSA',       'AGREGADO');

    -- -------------------------------------------------------------------------
    -- 3. INSERTAR O ACTUALIZAR EQUIPOS / PLACAS (lgTransportistaEquipo)
    -- -------------------------------------------------------------------------
    DECLARE @Placa VARCHAR(20), @Marca VARCHAR(50), @Color VARCHAR(30), @Transporte VARCHAR(100);
    DECLARE @idTranspAsoc VARCHAR(16), @NombreEquipo VARCHAR(100);

    DECLARE curEquipos CURSOR FOR
    SELECT DISTINCT UPPER(LTRIM(RTRIM(Placa))), UPPER(LTRIM(RTRIM(Marca))), UPPER(LTRIM(RTRIM(Color))), UPPER(LTRIM(RTRIM(Transporte)))
    FROM #TmpImport;

    OPEN curEquipos;
    FETCH NEXT FROM curEquipos INTO @Placa, @Marca, @Color, @Transporte;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @idTranspAsoc = CASE WHEN @Transporte = 'TRANSMELSA' THEN @idTransmelsa ELSE @idTransporteIvan END;
        SET @NombreEquipo = @Marca + ' ' + @Color;

        IF EXISTS (SELECT 1 FROM lgTransportistaEquipo WHERE UPPER(LTRIM(RTRIM(PlacaNo))) = @Placa)
        BEGIN
            UPDATE lgTransportistaEquipo
            SET idTransportista = @idTranspAsoc,
                TransportistaEquipo = @NombreEquipo,
                Status = 'ACTIVO'
            WHERE UPPER(LTRIM(RTRIM(PlacaNo))) = @Placa;

            PRINT 'Equipo con placa ' + @Placa + ' actualizado a transportista ID ' + @idTranspAsoc + ' (' + @NombreEquipo + ')';
        END
        ELSE
        BEGIN
            INSERT INTO lgTransportistaEquipo (
                idTransportistaEquipo, TransportistaEquipo, idTransportista,
                PlacaNo, PlacaVence, Status, Capacidad, idUnidad
            )
            VALUES (
                NEWID(), @NombreEquipo, @idTranspAsoc,
                @Placa, '2035-12-31', 'ACTIVO', 0.00, 'M3'
            );

            PRINT 'Equipo con placa ' + @Placa + ' insertado para transportista ID ' + @idTranspAsoc;
        END;

        FETCH NEXT FROM curEquipos INTO @Placa, @Marca, @Color, @Transporte;
    END;

    CLOSE curEquipos;
    DEALLOCATE curEquipos;

    -- -------------------------------------------------------------------------
    -- 4. INSERTAR O ACTUALIZAR CHOFERES (lgTransportistaChofer)
    -- -------------------------------------------------------------------------
    DECLARE @NombreChofer VARCHAR(100), @Cedula VARCHAR(30), @Producto VARCHAR(50);

    DECLARE curChoferes CURSOR FOR
    SELECT DISTINCT 
        UPPER(LTRIM(RTRIM(NombreChofer))), 
        UPPER(LTRIM(RTRIM(Cedula))), 
        UPPER(LTRIM(RTRIM(Transporte))),
        UPPER(LTRIM(RTRIM(Producto)))
    FROM #TmpImport;

    OPEN curChoferes;
    FETCH NEXT FROM curChoferes INTO @NombreChofer, @Cedula, @Transporte, @Producto;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @idTranspAsoc = CASE WHEN @Transporte = 'TRANSMELSA' THEN @idTransmelsa ELSE @idTransporteIvan END;

        DECLARE @CedulaLimpia VARCHAR(30) = REPLACE(REPLACE(@Cedula, '-', ''), ' ', '');

        DECLARE @idChoferExistente UNIQUEIDENTIFIER;
        SELECT TOP 1 @idChoferExistente = idTransportistaChofer
        FROM lgTransportistaChofer
        WHERE idTransportista = @idTranspAsoc
          AND (
              UPPER(LTRIM(RTRIM(TransportistaChofer))) = @NombreChofer
              OR (@CedulaLimpia <> '' AND REPLACE(REPLACE(ISNULL(LicenciaNo, ''), '-', ''), ' ', '') = @CedulaLimpia)
          );

        IF @idChoferExistente IS NOT NULL
        BEGIN
            UPDATE lgTransportistaChofer
            SET TransportistaChofer = @NombreChofer,
                LicenciaNo = @Cedula,
                Status = 'ACTIVO',
                Nota = 'PRODUCTO: ' + @Producto
            WHERE idTransportistaChofer = @idChoferExistente;

            PRINT 'Chofer ' + @NombreChofer + ' actualizado en transportista ID ' + @idTranspAsoc;
        END
        ELSE
        BEGIN
            INSERT INTO lgTransportistaChofer (
                idTransportistaChofer, idTransportista, TransportistaChofer,
                LicenciaVence, Status, LicenciaNo, Celular, Nota
            )
            VALUES (
                NEWID(), @idTranspAsoc, @NombreChofer,
                '2035-12-31', 'ACTIVO', @Cedula, NULL, 'PRODUCTO: ' + @Producto
            );

            PRINT 'Chofer ' + @NombreChofer + ' (' + @Cedula + ') insertado en transportista ID ' + @idTranspAsoc;
        END;

        FETCH NEXT FROM curChoferes INTO @NombreChofer, @Cedula, @Transporte, @Producto;
    END;

    CLOSE curChoferes;
    DEALLOCATE curChoferes;

    DROP TABLE #TmpImport;

    COMMIT TRANSACTION;
    PRINT '=======================================================';
    PRINT 'IMPORTACIÓN COMPLETADA CON ÉXITO EN CBSVMO.';
    PRINT '=======================================================';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    DECLARE @ErrMsg VARCHAR(MAX) = ERROR_MESSAGE();
    RAISERROR('Error durante la importación: %s', 16, 1, @ErrMsg);
END CATCH;
GO
