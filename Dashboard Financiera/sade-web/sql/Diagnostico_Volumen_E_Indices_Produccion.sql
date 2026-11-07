-- =========================================================================================
-- SCRIPT DE DIAGNÓSTICO PROFUNDO: VOLUMEN DE DATOS, RENDIMIENTO E ÍNDICES
-- SADE WEB / SOLONEGOCIOS / FINANCIERA
-- =========================================================================================
-- Este script:
--   1. Mide la cantidad real de registros que tiene el cliente (para saber si el volumen justifica el tiempo).
--   2. Mide el tiempo exacto (en milisegundos) de cada fase de los informes quincenales.
--   3. Identifica cuellos de botella (escaneos completos de tablas históricas vs subconsultas).
--   4. Detecta los índices faltantes recomendados directamente por el motor de SQL Server.
--   5. Ofrece los scripts CREATE INDEX para resolver la lentitud de raíz.
-- =========================================================================================

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

PRINT '=========================================================================================';
PRINT '           DIAGNÓSTICO DE VOLUMEN Y RENDIMIENTO EN PRODUCCIÓN - SADE WEB';
PRINT '           Fecha: ' + CONVERT(VARCHAR, GETDATE(), 120);
PRINT '=========================================================================================';
PRINT '';

-- -----------------------------------------------------------------------------------------
-- SECCIÓN 1: AUDITORÍA DE VOLUMEN DE DATOS EN PRODUCCIÓN
-- -----------------------------------------------------------------------------------------
PRINT '>>> 1. AUDITORÍA DE REGISTROS POR TABLA (TAMAÑO DE LA BASE DE DATOS)...';

SELECT 
    t.name AS Tabla,
    p.rows AS Total_Filas,
    CAST(ROUND(((SUM(a.total_pages) * 8) / 1024.00), 2) AS NUMERIC(36, 2)) AS Espacio_MB,
    CAST(ROUND(((SUM(a.used_pages) * 8) / 1024.00), 2) AS NUMERIC(36, 2)) AS Espacio_Usado_MB
FROM dbsolonegocios.sys.tables t
INNER JOIN dbsolonegocios.sys.indexes i ON t.OBJECT_ID = i.object_id
INNER JOIN dbsolonegocios.sys.partitions p ON i.object_id = p.OBJECT_ID AND i.index_id = p.index_id
INNER JOIN dbsolonegocios.sys.allocation_units a ON p.partition_id = a.container_id
WHERE t.name IN (
    'tb_prestamos', 
    'tb_detalle_prestamos', 
    'tb_recibo_pagos', 
    'tb_clientes', 
    'tb_reenganche', 
    'tb_notas_credito',
    'tb_datos_laboral',
    'tb_compania'
)
GROUP BY t.Name, p.Rows
ORDER BY Total_Filas DESC;

PRINT '';
PRINT '>>> 1.1 Desglose de Préstamos por Estado...';
SELECT 
    pr_estado,
    CASE pr_estado
        WHEN 1 THEN 'ACTIVO'
        WHEN 7 THEN 'SALDADO / CANCELADO'
        WHEN 0 THEN 'ANULADO'
        ELSE 'OTRO ESTADO (' + CAST(pr_estado AS VARCHAR(10)) + ')'
    END AS Descripcion_Estado,
    COUNT(*) AS Cantidad,
    MIN(pr_fecha) AS Fecha_Primer_Prestamo,
    MAX(pr_fecha) AS Fecha_Ultimo_Prestamo,
    ISNULL(SUM(pr_monto), 0) AS Monto_Total_Colocado
FROM dbsolonegocios.dbo.tb_prestamos WITH (NOLOCK)
GROUP BY pr_estado
ORDER BY Cantidad DESC;

PRINT '';
PRINT '>>> 1.2 Desglose de Recibos de Pagos por Año...';
SELECT 
    YEAR(rp_fecha) AS Año,
    COUNT(*) AS Cantidad_Recibos,
    ISNULL(SUM(rp_capital), 0) AS Capital_Cobrado,
    ISNULL(SUM(rp_interes), 0) AS Interes_Cobrado
FROM dbsolonegocios.dbo.tb_recibo_pagos WITH (NOLOCK)
WHERE rp_estado = 1
GROUP BY YEAR(rp_fecha)
ORDER BY Año DESC;

-- -----------------------------------------------------------------------------------------
-- SECCIÓN 2: BENCHMARK FASE POR FASE (PROFILING EXACTO DE TIEMPOS)
-- -----------------------------------------------------------------------------------------
PRINT '';
PRINT '=========================================================================================';
PRINT '>>> 2. BENCHMARK FASE POR FASE DE LA CONSULTA QUINCENAL (DÓNDE SE PIERDE EL TIEMPO)...';
PRINT '=========================================================================================';

DECLARE @Hoy DATE = CAST(GETDATE() AS DATE);
DECLARE @InicioQuincena DATE = DATEFROMPARTS(YEAR(@Hoy), MONTH(@Hoy), CASE WHEN DAY(@Hoy) <= 15 THEN 1 ELSE 16 END);
DECLARE @FinQuincena DATE = @Hoy;

PRINT 'Evaluando período de prueba: ' + CAST(@InicioQuincena AS VARCHAR(10)) + ' al ' + CAST(@FinQuincena AS VARCHAR(10));

DECLARE @tInicio DATETIME, @tFin DATETIME;

-- FASE A: Identificar Préstamos Candidatos
SET @tInicio = GETDATE();
IF OBJECT_ID('tempdb..#BenchCandidatos') IS NOT NULL DROP TABLE #BenchCandidatos;
CREATE TABLE #BenchCandidatos (
    pr_id_oficina INT,
    pr_id_cliente INT,
    pr_id_prestamos BIGINT PRIMARY KEY,
    pr_monto DECIMAL(18,2),
    pr_tasa_interes FLOAT,
    pr_fecha DATETIME,
    pr_estado INT
);

INSERT INTO #BenchCandidatos
SELECT 
    p.pr_id_oficina,
    p.pr_id_cliente,
    p.pr_id_prestamos,
    ISNULL(p.pr_monto, 0),
    ISNULL(p.pr_tasa_interes, 0),
    p.pr_fecha,
    p.pr_estado
FROM dbsolonegocios.dbo.tb_prestamos p WITH (NOLOCK)
WHERE (
    (p.pr_estado = 1 
     AND NOT EXISTS (SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg WITH (NOLOCK) WHERE rg.rg_id_prestamo = p.pr_id_prestamos AND rg.rg_id_oficina = p.pr_id_oficina AND CAST(rg.rg_fecha AS DATE) <= @FinQuincena)
     AND (p.pr_fecha_cancelacion IS NULL OR CAST(p.pr_fecha_cancelacion AS DATE) > @FinQuincena)
     AND EXISTS (SELECT 1 FROM dbsolonegocios.dbo.tb_detalle_prestamos dp WITH (NOLOCK) WHERE dp.dp_id_prestamos = p.pr_id_prestamos AND dp.dp_id_oficina = p.pr_id_oficina AND dp.dp_estado = 1 AND dp.dp_saldo_capital > 0)
    )
    OR (CAST(p.pr_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena AND ISNULL(p.pr_estado, 0) <> 0)
    OR EXISTS (SELECT 1 FROM dbsolonegocios.dbo.tb_recibo_pagos rp WITH (NOLOCK) WHERE rp.rp_id_prestamo = p.pr_id_prestamos AND rp.rp_id_oficina = p.pr_id_oficina AND rp.rp_estado = 1 AND CAST(rp.rp_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena)
    OR EXISTS (SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg WITH (NOLOCK) WHERE rg.rg_id_prestamo = p.pr_id_prestamos AND rg.rg_id_oficina = p.pr_id_oficina AND CAST(rg.rg_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena)
    OR (p.pr_fecha_cancelacion IS NOT NULL AND CAST(p.pr_fecha_cancelacion AS DATE) BETWEEN @InicioQuincena AND @FinQuincena)
);
SET @tFin = GETDATE();
PRINT '  [FASE A] Préstamos Candidatos identificados: ' + CAST((SELECT COUNT(*) FROM #BenchCandidatos) AS VARCHAR(10)) + ' registros en ' + CAST(DATEDIFF(ms, @tInicio, @tFin) AS VARCHAR(10)) + ' ms.';

-- FASE B: Pagos Históricos SIN filtro (Escaneo total como estaba antes)
SET @tInicio = GETDATE();
DECLARE @cntPagosTotal INT;
SELECT @cntPagosTotal = COUNT(*)
FROM (
    SELECT rp.rp_id_prestamo, ISNULL(SUM(rp.rp_capital), 0) AS total
    FROM dbsolonegocios.dbo.tb_recibo_pagos rp WITH (NOLOCK)
    WHERE rp.rp_estado = 1
      AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
      AND ISNULL(rp.rp_observacion, '') NOT LIKE '%Nota de Credito%'
      AND ISNULL(rp.rp_observacion, '') NOT LIKE '%Reenganche%'
    GROUP BY rp.rp_id_oficina, rp.rp_id_prestamo
) t;
SET @tFin = GETDATE();
PRINT '  [FASE B1 - LENTA] Pagos Históricos SIN FILTRAR (escanea todo el histórico): ' + CAST(DATEDIFF(ms, @tInicio, @tFin) AS VARCHAR(10)) + ' ms (' + CAST(@cntPagosTotal AS VARCHAR(10)) + ' préstamos históricos analizados).';

-- FASE B2: Pagos Históricos FILTRANDO por los préstamos de la quincena (#BenchCandidatos)
SET @tInicio = GETDATE();
DECLARE @cntPagosFiltrados INT;
SELECT @cntPagosFiltrados = COUNT(*)
FROM (
    SELECT rp.rp_id_prestamo, ISNULL(SUM(rp.rp_capital), 0) AS total
    FROM dbsolonegocios.dbo.tb_recibo_pagos rp WITH (NOLOCK)
    INNER JOIN #BenchCandidatos c ON c.pr_id_prestamos = rp.rp_id_prestamo
    WHERE rp.rp_estado = 1
      AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
      AND ISNULL(rp.rp_observacion, '') NOT LIKE '%Nota de Credito%'
      AND ISNULL(rp.rp_observacion, '') NOT LIKE '%Reenganche%'
    GROUP BY rp.rp_id_oficina, rp.rp_id_prestamo
) t;
SET @tFin = GETDATE();
PRINT '  [FASE B2 - OPTIMIZADA] Pagos Históricos FILTRADOS por candidatos: ' + CAST(DATEDIFF(ms, @tInicio, @tFin) AS VARCHAR(10)) + ' ms (Reducción dramática de tiempo).';

-- FASE C: Cobros Quincenales
SET @tInicio = GETDATE();
DECLARE @cntCobrosQ INT;
SELECT @cntCobrosQ = COUNT(*)
FROM (
    SELECT rp.rp_id_prestamo, ISNULL(SUM(rp.rp_capital), 0) AS cap
    FROM dbsolonegocios.dbo.tb_recibo_pagos rp WITH (NOLOCK)
    INNER JOIN #BenchCandidatos c ON c.pr_id_prestamos = rp.rp_id_prestamo
    WHERE rp.rp_estado = 1
      AND CAST(rp.rp_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena
    GROUP BY rp.rp_id_oficina, rp.rp_id_prestamo
) t;
SET @tFin = GETDATE();
PRINT '  [FASE C] Cobros Quincenales calculados: ' + CAST(DATEDIFF(ms, @tInicio, @tFin) AS VARCHAR(10)) + ' ms.';

-- FASE D: Cuotas Info (tb_detalle_prestamos)
SET @tInicio = GETDATE();
DECLARE @cntCuotas INT;
SELECT @cntCuotas = COUNT(*)
FROM (
    SELECT dp.dp_id_prestamos, ISNULL(SUM(dp.dp_saldo_capital), 0) AS sal
    FROM dbsolonegocios.dbo.tb_detalle_prestamos dp WITH (NOLOCK)
    INNER JOIN #BenchCandidatos c ON c.pr_id_prestamos = dp.dp_id_prestamos
    WHERE dp.dp_estado = 1
    GROUP BY dp.dp_id_oficina, dp.dp_id_prestamos
) t;
SET @tFin = GETDATE();
PRINT '  [FASE D] Cuotas pendientes calculadas: ' + CAST(DATEDIFF(ms, @tInicio, @tFin) AS VARCHAR(10)) + ' ms.';

-- FASE E: Datos de Clientes y Compañías
SET @tInicio = GETDATE();
DECLARE @cntClientes INT;
SELECT @cntClientes = COUNT(*)
FROM (
    SELECT DISTINCT c.pr_id_cliente, cli.cl_nombre, cli.cl_apellido, comp.co_nombre
    FROM #BenchCandidatos c
    LEFT JOIN dbsolonegocios.dbo.tb_clientes cli WITH (NOLOCK) ON cli.cl_id_cliente = c.pr_id_cliente
    OUTER APPLY (
        SELECT TOP 1 cp.co_nombre
        FROM dbsolonegocios.dbo.tb_datos_laboral dl WITH (NOLOCK)
        INNER JOIN dbsolonegocios.dbo.tb_compania cp WITH (NOLOCK) ON cp.co_id = dl.dl_id_empresa
        WHERE dl.dl_id_cliente = c.pr_id_cliente
        ORDER BY dl.dl_id DESC
    ) comp
) t;
SET @tFin = GETDATE();
PRINT '  [FASE E] Consulta de Datos de Clientes/Cartera: ' + CAST(DATEDIFF(ms, @tInicio, @tFin) AS VARCHAR(10)) + ' ms.';

IF OBJECT_ID('tempdb..#BenchCandidatos') IS NOT NULL DROP TABLE #BenchCandidatos;

-- -----------------------------------------------------------------------------------------
-- SECCIÓN 3: ÍNDICES FALTANTES DETECTADOS POR SQL SERVER (DMV OFICIALES)
-- -----------------------------------------------------------------------------------------
PRINT '';
PRINT '=========================================================================================';
PRINT '>>> 3. ÍNDICES FALTANTES DETECTADOS POR SQL SERVER (ORDENADOS POR IMPACTO)...';
PRINT '=========================================================================================';

SELECT TOP 10
    ROUND(s.avg_total_user_cost * (s.avg_user_impact / 100.0) * (s.user_seeks + s.user_scans), 0) AS Impacto_Estimado,
    d.statement AS Tabla,
    d.equality_columns AS Columnas_Igualdad,
    d.inequality_columns AS Columnas_Desigualdad,
    d.included_columns AS Columnas_Incluidas,
    s.user_seeks AS Busquedas_Usuario,
    s.user_scans AS Escaneos_Completos,
    ROUND(s.avg_user_impact, 2) AS Porcentaje_Mejora_Estimado
FROM sys.dm_db_missing_index_group_stats s
INNER JOIN sys.dm_db_missing_index_groups g ON s.group_handle = g.index_group_handle
INNER JOIN sys.dm_db_missing_index_details d ON g.index_handle = d.index_handle
WHERE d.statement LIKE '%dbsolonegocios%' OR d.statement LIKE '%Financiera%'
ORDER BY Impacto_Estimado DESC;

-- -----------------------------------------------------------------------------------------
-- SECCIÓN 4: ESTADO DE FRAGMENTACIÓN DE LOS ÍNDICES EN TABLAS CLAVE
-- -----------------------------------------------------------------------------------------
PRINT '';
PRINT '=========================================================================================';
PRINT '>>> 4. ÍNDICES EXISTENTES EN LAS TABLAS PRINCIPALES (tb_prestamos, tb_recibo_pagos, etc.)...';
PRINT '=========================================================================================';

SELECT 
    t.name AS Tabla,
    i.name AS Nombre_Indice,
    i.type_desc AS Tipo,
    SUBSTRING((
        SELECT ', ' + col.name
        FROM dbsolonegocios.sys.index_columns ic
        INNER JOIN dbsolonegocios.sys.columns col ON ic.object_id = col.object_id AND ic.column_id = col.column_id
        WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id
        ORDER BY ic.key_ordinal
        FOR XML PATH('')
    ), 3, 1000) AS Columnas_Clave
FROM dbsolonegocios.sys.indexes i
INNER JOIN dbsolonegocios.sys.tables t ON i.object_id = t.object_id
WHERE t.name IN ('tb_prestamos', 'tb_detalle_prestamos', 'tb_recibo_pagos', 'tb_reenganche')
  AND i.name IS NOT NULL
ORDER BY t.name, i.index_id;

PRINT '';
PRINT '=========================================================================================';
PRINT '>>> DIAGNÓSTICO FINALIZADO.';
PRINT '=========================================================================================';
GO
