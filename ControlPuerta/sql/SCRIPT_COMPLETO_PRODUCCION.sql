-- =============================================================================
-- SCRIPT COMPLETO CONSOLIDADO PARA PRODUCCIÓN
-- Control de Puerta y Recepción de Agregados
-- (Estructura corregida de tabla Defaults y división clara por Base de Datos)
-- =============================================================================

-- =============================================================================
-- BLOQUE 1: BASE DE DATOS PRINCIPAL / ERP (Ej. cbsvmotest / Tu Base ERP)
-- Ejecutar conectado a la base de datos principal de la empresa.
-- =============================================================================

-- 1.1 Columnas requeridas en prtEntradaCamion
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
CREATE OR ALTER PROCEDURE prtGenerarMovimientoEntrada
    @idEntradaCamion UNIQUEIDENTIFIER,
    @Usuario VARCHAR(100)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @idSuplidor VARCHAR(15), @Suplidor VARCHAR(200), @idAlmacen VARCHAR(20), @Referencia VARCHAR(100), @Placa VARCHAR(20);
    DECLARE @idProducto VARCHAR(50), @Producto VARCHAR(200), @Cantidad DECIMAL(18,4);
    DECLARE @idUnidad VARCHAR(20);
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
        @idUnidad = ISNULL(idUnidadAlmacen, ISNULL(idUnidad, 'UND'))
    FROM prtEntradaCamion 
    WHERE idEntradaCamion = @idEntradaCamion;

    IF NOT EXISTS(SELECT 1 FROM Almacen WHERE idAlmacen = @idAlmacen)
    BEGIN
        SELECT TOP 1 @idAlmacen = Valor FROM ConfiguracionPC WHERE Configuracion = 'ALMACENDEFAULT';
        IF @idAlmacen IS NULL OR NOT EXISTS(SELECT 1 FROM Almacen WHERE idAlmacen = @idAlmacen)
            SET @idAlmacen = 'GENERAL';
    END

    DECLARE @idProMovTipo INT = 1; 
    DECLARE @ProMovNum INT;
    SELECT @ProMovNum = ISNULL(MAX(TRY_CAST(ProMov AS INT)), 0) + 1 FROM promov WHERE ISNUMERIC(ProMov) = 1;
    DECLARE @ProMov VARCHAR(20) = CAST(@ProMovNum AS VARCHAR(20));
    DECLARE @Concepto VARCHAR(200) = 'Entrada por Conduce: ' + ISNULL(@Referencia,'') + ' - Placa: ' + ISNULL(@Placa,'');

    DECLARE @idProMov UNIQUEIDENTIFIER = NEWID();
    INSERT INTO promov (
        idProMov, idProMovTipo, ProMov, Fecha, Salida, Referencia, 
        Usuario, RecibidoPor, idAlmacen, Concepto, Nota, idSuplidor, Suplidor, Hora, Posteado
    )
    VALUES (
        @idProMov, @idProMovTipo, @ProMov, CAST(@Fecha AS DATE), 0, @Referencia,
        @Usuario, @Usuario, @idAlmacen, @Concepto, 'Generado automáticamente por Control de Puerta', 
        @idSuplidor, @Suplidor, @Fecha, 0
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


-- 1.5 Parámetros de Configuración ISO en Defaults (Estructura real: Clave, Valor, Categoria, UidClave)
IF NOT EXISTS (SELECT 1 FROM Defaults WHERE Categoria = 'ISO' AND Clave = 'IDENTIFICADOR')
BEGIN
    INSERT INTO Defaults (Categoria, Clave, Valor, Descripcion, UidClave, Tipo)
    VALUES ('ISO', 'IDENTIFICADOR', CAST('FE-GC-02' AS sql_variant), 'Identificador de formulario ISO', NEWID(), 'C');
    PRINT 'Parámetro ISO IDENTIFICADOR insertado en Defaults';
END
ELSE
BEGIN
    UPDATE Defaults 
    SET Valor = CAST('FE-GC-02' AS sql_variant)
    WHERE Categoria = 'ISO' AND Clave = 'IDENTIFICADOR';
    PRINT 'Parámetro ISO IDENTIFICADOR actualizado en Defaults';
END;
GO

IF NOT EXISTS (SELECT 1 FROM Defaults WHERE Categoria = 'ISO' AND Clave = 'REVISION')
BEGIN
    INSERT INTO Defaults (Categoria, Clave, Valor, Descripcion, UidClave, Tipo)
    VALUES ('ISO', 'REVISION', CAST('03' AS sql_variant), 'Numero de revision ISO', NEWID(), 'C');
    PRINT 'Parámetro ISO REVISION insertado en Defaults';
END
ELSE
BEGIN
    UPDATE Defaults 
    SET Valor = CAST('03' AS sql_variant)
    WHERE Categoria = 'ISO' AND Clave = 'REVISION';
    PRINT 'Parámetro ISO REVISION actualizado en Defaults';
END;
GO


-- =============================================================================
-- BLOQUE 2: BASE DE DATOS DE EVIDENCIAS (SADE_Evidencias)
-- Ejecutar conectado a la base de datos SADE_Evidencias
-- =============================================================================
-- USE [SADE_Evidencias];
-- GO

IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'Evidencias' AND COLUMN_NAME = 'FotoCamion')
BEGIN
    ALTER TABLE Evidencias ADD FotoCamion VARBINARY(MAX) NULL;
    PRINT 'Agregada columna FotoCamion a tabla Evidencias';
END;
GO

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
