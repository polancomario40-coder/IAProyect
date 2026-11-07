USE sws;
GO

-- ==========================================================
-- 1. Tabla Principal: CutTickets (Cabecera de la Orden de Corte)
-- ==========================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'CutTickets')
BEGIN
    CREATE TABLE CutTickets (
        IdCutTicket INT IDENTITY(1,1) PRIMARY KEY,
        CutNumber VARCHAR(50) NOT NULL UNIQUE,       -- Ej: 'MTO-13111', 'MTO-13114'
        Style VARCHAR(100) NOT NULL,                 -- Ej: '199PF-SPUN-PW (LIZ)', '2553E-SN-NP'
        Customer VARCHAR(100) NULL,                  -- Ej: 'ARAMARK-HQ', 'CINTAS'
        GerberModel VARCHAR(100) NULL,               -- Ej: 'M199', '250EANWPK1'
        Folder VARCHAR(100) NULL,                    -- Ej: 'CHEFCOAT', 'MSHIRTS'
        Fabric VARCHAR(150) NULL,                    -- Ej: 'RF-SPUN PLAIN 7 OZ. WHT-LIZ'
        FabricDesc VARCHAR(255) NULL,                -- Descripción de tela
        Mill VARCHAR(100) NULL,                      -- Molino / Proveedor (ej: 'Liztex')
        CuttableWidth VARCHAR(50) NULL,              -- Ancho utilizable (ej: '64"', '61.5"')
        TotalUnits INT NOT NULL DEFAULT 0,           -- Total unidades del corte
        OrderDate DATETIME NULL,                     -- Fecha del ticket
        CutDate DATETIME NULL,                       -- Fecha de corte
        RequireShipDate DATETIME NULL,               -- Fecha requerida de embarque
        SpecialInstructions NVARCHAR(MAX) NULL,      -- Instrucciones de confección/corte
        Status VARCHAR(50) NOT NULL DEFAULT 'PENDIENTE_CORTE', -- PENDIENTE_CORTE, CORTADO, COSIENDO, INSPECCION, EMPAQUE, COMPLETADO, EMBARCADO
        SourceFileName VARCHAR(255) NULL,            -- Nombre del archivo Excel de origen
        CreatedAt DATETIME NOT NULL DEFAULT GETDATE(),
        UpdatedAt DATETIME NOT NULL DEFAULT GETDATE()
    );

    CREATE INDEX IX_CutTickets_Status ON CutTickets(Status);
    CREATE INDEX IX_CutTickets_Customer ON CutTickets(Customer);
    CREATE INDEX IX_CutTickets_Style ON CutTickets(Style);
END
GO

-- ==========================================================
-- 2. Tabla: CutTicketMarkers (Trazos / Marcadores del Corte)
-- ==========================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'CutTicketMarkers')
BEGIN
    CREATE TABLE CutTicketMarkers (
        IdMarker INT IDENTITY(1,1) PRIMARY KEY,
        IdCutTicket INT NOT NULL FOREIGN KEY REFERENCES CutTickets(IdCutTicket) ON DELETE CASCADE,
        MarkerName VARCHAR(100) NOT NULL,            -- Ej: 'M199-6466', '25NE-615-024'
        FabricWidth VARCHAR(50) NULL,                -- Ej: '64"', '61.5"'
        MarkerLength DECIMAL(10,2) NULL,             -- Longitud del trazo en yardas
        Efficiency DECIMAL(6,2) NULL,                -- % Eficiencia (ej: 75.72, 84.92)
        Plies INT NOT NULL DEFAULT 0,                -- Cantidad de lienzos
        CreatedAt DATETIME NOT NULL DEFAULT GETDATE()
    );

    CREATE INDEX IX_CutTicketMarkers_CutTicket ON CutTicketMarkers(IdCutTicket);
END
GO

-- ==========================================================
-- 3. Tabla: CutTicketDetails (Desglose por Tallas y Cantidades)
-- ==========================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'CutTicketDetails')
BEGIN
    CREATE TABLE CutTicketDetails (
        IdCutDetail INT IDENTITY(1,1) PRIMARY KEY,
        IdCutTicket INT NOT NULL FOREIGN KEY REFERENCES CutTickets(IdCutTicket) ON DELETE CASCADE,
        IdMarker INT NULL FOREIGN KEY REFERENCES CutTicketMarkers(IdMarker),
        Size VARCHAR(20) NOT NULL,                   -- Ej: 'XS', 'S', 'M', 'L', 'XL', '2XL', '3XL'
        Ratio INT NOT NULL DEFAULT 0,                -- Proporción por trazo
        Units INT NOT NULL DEFAULT 0,                -- Unidades totales (Lienzos * Ratio)
        CreatedAt DATETIME NOT NULL DEFAULT GETDATE()
    );

    CREATE INDEX IX_CutTicketDetails_CutTicket ON CutTicketDetails(IdCutTicket);
    CREATE INDEX IX_CutTicketDetails_Size ON CutTicketDetails(Size);
END
GO

-- ==========================================================
-- 4. Tabla: CutTicketStatusHistory (Historial / Bitácora WIP)
-- ==========================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'CutTicketStatusHistory')
BEGIN
    CREATE TABLE CutTicketStatusHistory (
        IdHistory INT IDENTITY(1,1) PRIMARY KEY,
        IdCutTicket INT NOT NULL FOREIGN KEY REFERENCES CutTickets(IdCutTicket) ON DELETE CASCADE,
        PreviousStatus VARCHAR(50) NULL,
        NewStatus VARCHAR(50) NOT NULL,
        ChangedBy VARCHAR(100) NOT NULL DEFAULT 'SYSTEM',
        Notes NVARCHAR(500) NULL,
        ChangedAt DATETIME NOT NULL DEFAULT GETDATE()
    );

    CREATE INDEX IX_CutTicketHistory_CutTicket ON CutTicketStatusHistory(IdCutTicket);
END
GO

-- ==========================================================
-- 5. Tabla: CutTicketBundles (Paquetes / Etiquetas para Fases 3 y 4)
-- ==========================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'CutTicketBundles')
BEGIN
    CREATE TABLE CutTicketBundles (
        IdBundle INT IDENTITY(1,1) PRIMARY KEY,
        IdCutTicket INT NOT NULL FOREIGN KEY REFERENCES CutTickets(IdCutTicket) ON DELETE CASCADE,
        Barcode VARCHAR(50) NOT NULL UNIQUE,         -- ID legible por escáner (ej: 'TKT-13111-001')
        BundleNumber INT NOT NULL,                   -- Número correlativo del paquete
        Size VARCHAR(20) NOT NULL,                   -- Talla del paquete
        Quantity INT NOT NULL,                       -- Cantidad de prendas en el bulto
        Status VARCHAR(50) NOT NULL DEFAULT 'PENDIENTE', -- PENDIENTE, EN_COSTURA, EMPACADO, EMBARCADO
        ScannedAt DATETIME NULL,                     -- Fecha/hora cuando se escaneó en empaque
        CreatedAt DATETIME NOT NULL DEFAULT GETDATE()
    );

    CREATE INDEX IX_CutTicketBundles_Barcode ON CutTicketBundles(Barcode);
    CREATE INDEX IX_CutTicketBundles_CutTicket ON CutTicketBundles(IdCutTicket);
END
GO
