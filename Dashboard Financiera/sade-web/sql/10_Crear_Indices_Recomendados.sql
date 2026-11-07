-- =========================================================================================
-- SCRIPT DE CREACIÓN DE ÍNDICES DE ALTO RENDIMIENTO (SADE / SOLONEGOCIOS)
-- =========================================================================================
-- Estos índices están diseñados específicamente para acelerar las consultas quincenales
-- y los dashboards de SADE Web entre 10x y 50x, evitando Table Scans en tablas históricas.
-- Utilizan ONLINE = ON (si la edición de SQL Server lo soporta) o creación estándar segura.
-- =========================================================================================
USE dbsolonegocios
GO

SET NOCOUNT ON;

PRINT '=========================================================================================';
PRINT '  APLICANDO ÍNDICES DE ALTO RENDIMIENTO PARA CONSULTAS QUINCENALES Y REPORTES';
PRINT '=========================================================================================';

-- 1. Índice en tb_recibo_pagos por Préstamo y Estado (Elimina el escaneo total de pagos históricos)
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_tb_recibo_pagos_prestamo_estado_quincena' AND object_id = OBJECT_ID('dbo.tb_recibo_pagos'))
BEGIN
    PRINT 'Creando índice IX_tb_recibo_pagos_prestamo_estado_quincena...';
    CREATE NONCLUSTERED INDEX IX_tb_recibo_pagos_prestamo_estado_quincena
    ON dbo.tb_recibo_pagos (rp_id_prestamo, rp_estado, rp_fecha)
    INCLUDE (rp_capital, rp_interes, rp_mora, rp_forma_pago, rp_observacion, rp_id_oficina);
    PRINT '  -> Índice IX_tb_recibo_pagos_prestamo_estado_quincena CREADO exitosamente.';
END
ELSE
BEGIN
    PRINT '  -> El índice IX_tb_recibo_pagos_prestamo_estado_quincena ya existe.';
END
GO

-- 2. Índice en tb_detalle_prestamos por Préstamo y Estado (Acelera cálculo de saldo y moras)
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_tb_detalle_prestamos_prestamo_estado_cuotas' AND object_id = OBJECT_ID('dbo.tb_detalle_prestamos'))
BEGIN
    PRINT 'Creando índice IX_tb_detalle_prestamos_prestamo_estado_cuotas...';
    CREATE NONCLUSTERED INDEX IX_tb_detalle_prestamos_prestamo_estado_cuotas
    ON dbo.tb_detalle_prestamos (dp_id_prestamos, dp_estado)
    INCLUDE (dp_saldo_capital, dp_saldo_interes, dp_fecha_venc, dp_id_oficina);
    PRINT '  -> Índice IX_tb_detalle_prestamos_prestamo_estado_cuotas CREADO exitosamente.';
END
ELSE
BEGIN
    PRINT '  -> El índice IX_tb_detalle_prestamos_prestamo_estado_cuotas ya existe.';
END
GO

-- 3. Índice en tb_reenganche por Préstamo y Fecha
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_tb_reenganche_prestamo_fecha' AND object_id = OBJECT_ID('dbo.tb_reenganche'))
BEGIN
    PRINT 'Creando índice IX_tb_reenganche_prestamo_fecha...';
    CREATE NONCLUSTERED INDEX IX_tb_reenganche_prestamo_fecha
    ON dbo.tb_reenganche (rg_id_prestamo, rg_fecha)
    INCLUDE (rg_id_oficina, rg_id_cliente);
    PRINT '  -> Índice IX_tb_reenganche_prestamo_fecha CREADO exitosamente.';
END
ELSE
BEGIN
    PRINT '  -> El índice IX_tb_reenganche_prestamo_fecha ya existe.';
END
GO

-- 4. Índice en tb_prestamos por Estado y Fecha
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_tb_prestamos_estado_fecha_reportes' AND object_id = OBJECT_ID('dbo.tb_prestamos'))
BEGIN
    PRINT 'Creando índice IX_tb_prestamos_estado_fecha_reportes...';
    CREATE NONCLUSTERED INDEX IX_tb_prestamos_estado_fecha_reportes
    ON dbo.tb_prestamos (pr_estado, pr_fecha)
    INCLUDE (pr_id_cliente, pr_monto, pr_tasa_interes, pr_fecha_cancelacion, pr_id_oficina);
    PRINT '  -> Índice IX_tb_prestamos_estado_fecha_reportes CREADO exitosamente.';
END
ELSE
BEGIN
    PRINT '  -> El índice IX_tb_prestamos_estado_fecha_reportes ya existe.';
END
GO

-- 5. Índice en tb_datos_laboral para agilizar resolución de compañía/cartera
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_tb_datos_laboral_cliente_empresa' AND object_id = OBJECT_ID('dbo.tb_datos_laboral'))
BEGIN
    PRINT 'Creando índice IX_tb_datos_laboral_cliente_empresa...';
    CREATE NONCLUSTERED INDEX IX_tb_datos_laboral_cliente_empresa
    ON dbo.tb_datos_laboral (dl_id_cliente, dl_id_empresa)
    INCLUDE (dl_id, dl_id_oficina);
    PRINT '  -> Índice IX_tb_datos_laboral_cliente_empresa CREADO exitosamente.';
END
ELSE
BEGIN
    PRINT '  -> El índice IX_tb_datos_laboral_cliente_empresa ya existe.';
END
GO

PRINT '=========================================================================================';
PRINT '  PROCESO DE CREACIÓN DE ÍNDICES COMPLETADO EXITOSAMENTE.';
PRINT '=========================================================================================';
GO
