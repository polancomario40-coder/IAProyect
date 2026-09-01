-- ============================================================
-- Script: 02_schema_evidencias.sql
-- Base de Datos: SADE_Evidencias (INDEPENDIENTE del ERP)
-- Descripción: Almacenamiento de evidencias fotográficas,
--              firmas digitales y documentos firmados del
--              Módulo de Control de Puerta.
-- IMPORTANTE: Esta BD es INDEPENDIENTE de AdelH/Financiera.
--             Solo guarda binarios e información de referencia.
--             El idEvidencia es la clave de enlace cross-BD.
-- ============================================================

-- Crear la base de datos si no existe
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'SADE_Evidencias')
BEGIN
    CREATE DATABASE SADE_Evidencias
        COLLATE SQL_Latin1_General_CP1_CI_AS;
    PRINT 'Base de datos SADE_Evidencias creada.';
END
ELSE
    PRINT 'Base de datos SADE_Evidencias ya existe.';
GO

USE SADE_Evidencias;
GO

-- ============================================================
-- Tabla principal de evidencias
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Evidencias')
BEGIN
    CREATE TABLE Evidencias (
        idEvidencia         UNIQUEIDENTIFIER    NOT NULL CONSTRAINT PK_Evidencias PRIMARY KEY DEFAULT NEWID(),

        -- Referencia al módulo de origen (cross-BD por GUID)
        TipoModulo          NVARCHAR(50)        NOT NULL DEFAULT 'CONTROL_PUERTA',
        idRefExterna        UNIQUEIDENTIFIER    NOT NULL,       -- idEntradaCamion en AdelH
        Referencia          NVARCHAR(100)       NOT NULL,       -- Número de conduce

        -- Foto del conduce físico (tomada por cámara o upload)
        FotoConduce         VARBINARY(MAX)      NULL,
        FotoConduceMime     NVARCHAR(50)        NULL DEFAULT 'image/jpeg',
        FotoConduceNombre   NVARCHAR(200)       NULL,

        -- Firma digital (canvas PNG base64 convertido)
        FirmaDigital        VARBINARY(MAX)      NULL,
        FirmaDigitalMime    NVARCHAR(50)        NULL DEFAULT 'image/png',

        -- Imagen final: conduce con firma superpuesta
        ImagenFirmada       VARBINARY(MAX)      NULL,
        ImagenFirmadaMime   NVARCHAR(50)        NULL DEFAULT 'image/jpeg',

        -- Foto del camión/placa (captura OCR)
        FotoCamion          VARBINARY(MAX)      NULL,
        FotoCamionMime      NVARCHAR(50)        NULL DEFAULT 'image/jpeg',

        -- Metadatos en JSON (placa, chofer, transportista, coordenadas GPS futuro)
        Metadatos           NVARCHAR(2000)      NULL,

        -- Auditoría
        FechaCaptura        DATETIME2(0)        NOT NULL DEFAULT GETDATE(),
        Usuario             NVARCHAR(50)        NOT NULL,
        IpOrigen            NVARCHAR(45)        NULL,
        Activo              BIT                 NOT NULL DEFAULT 1
    );

    CREATE INDEX IX_Evidencias_idRefExterna ON Evidencias (idRefExterna);
    CREATE INDEX IX_Evidencias_Referencia   ON Evidencias (Referencia);
    CREATE INDEX IX_Evidencias_FechaCaptura ON Evidencias (FechaCaptura);

    PRINT 'Tabla Evidencias creada correctamente.';
END
ELSE
    PRINT 'Tabla Evidencias ya existe — sin cambios.';
GO

-- ============================================================
-- SP: Guardar evidencia completa
-- ============================================================
CREATE OR ALTER PROCEDURE evGuardarEvidencia
    @idEvidencia        UNIQUEIDENTIFIER,
    @idRefExterna       UNIQUEIDENTIFIER,
    @Referencia         NVARCHAR(100),
    @FotoConduce        VARBINARY(MAX)  = NULL,
    @FotoConduceMime    NVARCHAR(50)    = 'image/jpeg',
    @FotoConduceNombre  NVARCHAR(200)  = NULL,
    @FirmaDigital       VARBINARY(MAX)  = NULL,
    @ImagenFirmada      VARBINARY(MAX)  = NULL,
    @FotoCamion         VARBINARY(MAX)  = NULL,
    @Metadatos          NVARCHAR(2000)  = NULL,
    @Usuario            NVARCHAR(50),
    @IpOrigen           NVARCHAR(45)    = NULL
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (SELECT 1 FROM Evidencias WHERE idEvidencia = @idEvidencia)
    BEGIN
        -- Actualizar evidencia existente (puede añadir firma después)
        UPDATE Evidencias SET
            FotoConduce         = ISNULL(@FotoConduce, FotoConduce),
            FotoConduceMime     = ISNULL(@FotoConduceMime, FotoConduceMime),
            FotoConduceNombre   = ISNULL(@FotoConduceNombre, FotoConduceNombre),
            FirmaDigital        = ISNULL(@FirmaDigital, FirmaDigital),
            ImagenFirmada       = ISNULL(@ImagenFirmada, ImagenFirmada),
            FotoCamion          = ISNULL(@FotoCamion, FotoCamion),
            Metadatos           = ISNULL(@Metadatos, Metadatos)
        WHERE idEvidencia = @idEvidencia;
    END
    ELSE
    BEGIN
        INSERT INTO Evidencias (
            idEvidencia, idRefExterna, Referencia,
            FotoConduce, FotoConduceMime, FotoConduceNombre,
            FirmaDigital, ImagenFirmada, FotoCamion,
            Metadatos, Usuario, IpOrigen
        ) VALUES (
            @idEvidencia, @idRefExterna, @Referencia,
            @FotoConduce, @FotoConduceMime, @FotoConduceNombre,
            @FirmaDigital, @ImagenFirmada, @FotoCamion,
            @Metadatos, @Usuario, @IpOrigen
        );
    END;

    SELECT @idEvidencia AS idEvidencia;
END;
GO

-- SP: Obtener evidencia por ID
CREATE OR ALTER PROCEDURE evObtenerEvidencia
    @idEvidencia UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        idEvidencia, TipoModulo, idRefExterna, Referencia,
        FotoConduceMime, FotoConduceNombre,
        CASE WHEN FotoConduce IS NOT NULL THEN 1 ELSE 0 END AS TieneFoto,
        CASE WHEN FirmaDigital IS NOT NULL THEN 1 ELSE 0 END AS TieneFirma,
        CASE WHEN ImagenFirmada IS NOT NULL THEN 1 ELSE 0 END AS TieneImagenFirmada,
        CASE WHEN FotoCamion IS NOT NULL THEN 1 ELSE 0 END AS TieneFotoCamion,
        Metadatos, FechaCaptura, Usuario
    FROM Evidencias
    WHERE idEvidencia = @idEvidencia AND Activo = 1;
END;
GO

PRINT '=== Scripts de SADE_Evidencias aplicados correctamente ===';
