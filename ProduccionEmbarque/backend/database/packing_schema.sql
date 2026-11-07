USE sws;
GO

-- ==========================================================
-- 1. Tabla PackingLists (Contenedores y Manifiestos de Embarque)
-- ==========================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'PackingLists')
BEGIN
    CREATE TABLE PackingLists (
        IdPackingList INT IDENTITY(1,1) PRIMARY KEY,
        ContainerNumber VARCHAR(50) NOT NULL UNIQUE,       -- Ej: 'BMOU-578710-1'
        Customer VARCHAR(100) NULL,
        ShipDate DATETIME NULL,
        Status VARCHAR(50) NOT NULL DEFAULT 'ABIERTO',     -- 'ABIERTO', 'DESPACHADO'
        Notes NVARCHAR(500) NULL,
        CreatedAt DATETIME NOT NULL DEFAULT GETDATE(),
        UpdatedAt DATETIME NOT NULL DEFAULT GETDATE()
    );

    CREATE INDEX IX_PackingLists_Container ON PackingLists(ContainerNumber);
    CREATE INDEX IX_PackingLists_Status ON PackingLists(Status);
END
GO

-- ==========================================================
-- 2. Actualizar CutTicketBundles con columnas de Empaque
-- ==========================================================
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('CutTicketBundles') AND name = 'IdPackingList')
BEGIN
    ALTER TABLE CutTicketBundles ADD IdPackingList INT NULL FOREIGN KEY REFERENCES PackingLists(IdPackingList);
END
GO

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('CutTicketBundles') AND name = 'BoxNumber')
BEGIN
    ALTER TABLE CutTicketBundles ADD BoxNumber INT NULL DEFAULT 1;
END
GO
