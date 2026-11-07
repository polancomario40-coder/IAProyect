-- =========================================================================================
-- SCRIPT DE CONCILIACION Y DIAGNOSTICO: DBSOLONEGOCIOS vs FINANCIERA (PRODUCCION)
-- =========================================================================================
-- Instrucciones para el Administrador / Programador:
--   1. Abrir SQL Server Management Studio (SSMS).
--   2. Conectarse a la instancia de SQL Server de PRODUCCION.
--   3. Abrir este archivo y presionar F5 (Ejecutar).
--   4. Exportar o copiar los resultados (grid o texto) y enviarnoslos.
--
-- NOTA DE PRIVACIDAD:
--   Este script NO extrae nombres, cedulas, telefonos ni datos personales confidenciales.
--   Solo extrae sumatorias agregadas, conteos de control y cuadre entre ambas bases de datos.
-- =========================================================================================

SET NOCOUNT ON;

PRINT '=========================================================================================';
PRINT '   REPORTE DE DIAGNOSTICO Y CONCILIACION: DBSOLONEGOCIOS <--> FINANCIERA';
PRINT '   Servidor: ' + @@SERVERNAME;
PRINT '   Fecha de ejecucion: ' + CONVERT(VARCHAR(30), GETDATE(), 120);
PRINT '=========================================================================================';
PRINT '';

-- =========================================================================================
-- SECCION 1: CONCILIACION DE CARTERA ACTIVA (KPI CARTERA)
-- =========================================================================================
PRINT '>>> 1. CONCILIACION DE CARTERA ACTIVA: tb_prestamos vs Financiera.dbo.Cxc';

-- 1.1 Desde dbsolonegocios (Fuente Primaria Financiera)
SELECT 
    '1.1 dbsolonegocios (tb_prestamos)' AS Origen,
    COUNT(*) AS TotalPrestamosRegistrados,
    SUM(CASE WHEN pr_estado = 1 THEN 1 ELSE 0 END) AS PrestamosActivos_Estado1,
    SUM(CASE WHEN pr_estado <> 1 THEN 1 ELSE 0 END) AS PrestamosInactivosOSaldados,
    CAST(SUM(CASE WHEN pr_estado = 1 THEN pr_monto ELSE 0 END) AS DECIMAL(18,2)) AS CapitalActivoOriginal,
    CAST(SUM(CASE WHEN pr_estado = 1 THEN pr_interes ELSE 0 END) AS DECIMAL(18,2)) AS InteresActivoProyectado,
    CAST(SUM(CASE WHEN pr_estado = 1 THEN pr_balance ELSE 0 END) AS DECIMAL(18,2)) AS BalanceActivoTotal_SoloNegocios
FROM dbsolonegocios.dbo.tb_prestamos;

-- 1.2 Desde dbsolonegocios (tb_detalle_prestamos - cuotas)
SELECT 
    '1.2 dbsolonegocios (tb_detalle_prestamos)' AS Origen,
    COUNT(DISTINCT dp_id_prestamos) AS PrestamosConCuotas,
    CAST(SUM(dp_capital) AS DECIMAL(18,2)) AS CapitalOriginalTotalCuotas,
    CAST(SUM(dp_saldo_capital) AS DECIMAL(18,2)) AS SaldoCapitalPendienteCuotas,
    CAST(SUM(dp_saldo_interes) AS DECIMAL(18,2)) AS SaldoInteresPendienteCuotas,
    CAST(SUM(dp_saldo_capital + dp_saldo_interes) AS DECIMAL(18,2)) AS BalanceTotalPendienteCuotas
FROM dbsolonegocios.dbo.tb_detalle_prestamos dp
WHERE EXISTS (SELECT 1 FROM dbsolonegocios.dbo.tb_prestamos p WHERE p.pr_id_prestamos = dp.dp_id_prestamos AND p.pr_estado = 1);

-- 1.3 Desde Financiera.dbo.Cxc (Facturas FT)
SELECT 
    '1.3 Financiera (dbo.Cxc FT)' AS Origen,
    COUNT(*) AS TotalFT_EnFinanciera,
    SUM(CASE WHEN Cancelado = 0 THEN 1 ELSE 0 END) AS TotalFT_NoCanceladas,
    SUM(CASE WHEN Cancelado = 1 THEN 1 ELSE 0 END) AS TotalFT_Canceladas,
    CAST(SUM(CASE WHEN Cancelado = 0 THEN Valor ELSE 0 END) AS DECIMAL(18,2)) AS ValorTotal_FT_NoCanceladas
FROM Financiera.dbo.Cxc
WHERE idTipoDocumento = 'FT';

-- 1.4 Verificacion de si hay FT en Financiera que NO son prestamos (facturacion comercial de la empresa)
;WITH PrestamosSoloNegocios AS (
    SELECT DISTINCT CAST(pr_id_prestamos AS VARCHAR(20)) AS idPrestamo
    FROM dbsolonegocios.dbo.tb_prestamos
)
SELECT 
    '1.4 Cruce FT vs tb_prestamos' AS Origen,
    COUNT(*) AS TotalFT_Financiera,
    SUM(CASE WHEN p.idPrestamo IS NOT NULL THEN 1 ELSE 0 END) AS FT_QueVienenDeSoloNegocios,
    SUM(CASE WHEN p.idPrestamo IS NULL THEN 1 ELSE 0 END) AS FT_AjenasOComercialesDelERP,
    CAST(SUM(CASE WHEN p.idPrestamo IS NOT NULL AND c.Cancelado = 0 THEN c.Valor ELSE 0 END) AS DECIMAL(18,2)) AS MontoFT_SoloNegociosActivas,
    CAST(SUM(CASE WHEN p.idPrestamo IS NULL AND c.Cancelado = 0 THEN c.Valor ELSE 0 END) AS DECIMAL(18,2)) AS MontoFT_AjenasActivas
FROM Financiera.dbo.Cxc c
LEFT JOIN PrestamosSoloNegocios p 
    ON p.idPrestamo = c.idDocumento OR p.idPrestamo = c.Cxc
WHERE c.idTipoDocumento = 'FT';


-- =========================================================================================
-- SECCION 2: CONCILIACION DE COBROS DEL MES ACTUAL (KPI COBRADO ESTE MES)
-- =========================================================================================
PRINT '>>> 2. CONCILIACION DE COBROS DEL MES ACTUAL';

DECLARE @InicioMes DATE = DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1);
DECLARE @FinMes    DATE = EOMONTH(GETDATE());

-- 2.1 Cobros en dbsolonegocios
SELECT 
    '2.1 dbsolonegocios (tb_recibo_pagos)' AS Origen,
    COUNT(*) AS TotalRecibosMes,
    CAST(SUM(rp_capital) AS DECIMAL(18,2)) AS CapitalCobradoMes,
    CAST(SUM(rp_interes) AS DECIMAL(18,2)) AS InteresCobradoMes,
    CAST(SUM(rp_mora) AS DECIMAL(18,2)) AS MoraCobradaMes,
    CAST(SUM(rp_total_pagado) AS DECIMAL(18,2)) AS TotalCobradoMes_SoloNegocios
FROM dbsolonegocios.dbo.tb_recibo_pagos
WHERE CAST(rp_fecha AS DATE) BETWEEN @InicioMes AND @FinMes
  AND rp_estado = 1;

-- 2.2 Cobros en Financiera (Cxc RC)
SELECT 
    '2.2 Financiera (dbo.Cxc RC)' AS Origen,
    COUNT(*) AS TotalRecibosRC_EnFinanciera,
    CAST(SUM(Valor) AS DECIMAL(18,2)) AS TotalCobradoMes_EnFinanciera
FROM Financiera.dbo.Cxc
WHERE idTipoDocumento = 'RC'
  AND Cancelado = 0
  AND CAST(Fecha AS DATE) BETWEEN @InicioMes AND @FinMes;

-- 2.3 Aplicaciones en CxcDet (ver si hay multiplicacion)
SELECT 
    '2.3 Financiera (dbo.CxcDet)' AS Origen,
    COUNT(DISTINCT d.idCxc) AS CantidadRecibosConDetalle,
    COUNT(*) AS TotalLineasDetalle,
    CAST(SUM(d.Valor) AS DECIMAL(18,2)) AS TotalMontoAplicadoEnCxcDet
FROM Financiera.dbo.CxcDet d
JOIN Financiera.dbo.Cxc rc ON rc.idCxc = d.idCxc
WHERE rc.idTipoDocumento = 'RC'
  AND rc.Cancelado = 0
  AND CAST(rc.Fecha AS DATE) BETWEEN @InicioMes AND @FinMes;


-- =========================================================================================
-- SECCION 3: CONCILIACION DE CLIENTES (HISTORICOS vs ACTIVOS)
-- =========================================================================================
PRINT '>>> 3. CONCILIACION DE CLIENTES ACTIVOS vs HISTORICOS';

SELECT 
    (SELECT COUNT(*) FROM dbsolonegocios.dbo.tb_clientes) AS ClientesHistoricos_SoloNegocios,
    (SELECT COUNT(DISTINCT pr_id_cliente) FROM dbsolonegocios.dbo.tb_prestamos WHERE pr_estado = 1) AS ClientesConPrestamosActivos_SoloNegocios,
    (SELECT COUNT(*) FROM Financiera.dbo.Cliente) AS ClientesHistoricos_Financiera,
    (SELECT COUNT(DISTINCT idCliente) FROM Financiera.dbo.Cxc WHERE idTipoDocumento = 'FT' AND Cancelado = 0) AS ClientesConPrestamosActivos_Financiera;

-- 3.2 Clasificacion de clientes SOLO para aquellos con prestamos ACTIVOS
;WITH ClientesActivos AS (
    SELECT DISTINCT pr_id_cliente
    FROM dbsolonegocios.dbo.tb_prestamos
    WHERE pr_estado = 1
),
ConteoPrestamosCliente AS (
    SELECT pr_id_cliente, COUNT(*) AS TotalHistoricoPrestamos
    FROM dbsolonegocios.dbo.tb_prestamos
    GROUP BY pr_id_cliente
)
SELECT 
    '3.2 Clasificacion de Clientes ACTIVOS' AS Concepto,
    COUNT(*) AS TotalClientesActivos,
    SUM(CASE WHEN cp.TotalHistoricoPrestamos <= 1 THEN 1 ELSE 0 END) AS Nuevos_Activos,
    SUM(CASE WHEN cp.TotalHistoricoPrestamos > 1 THEN 1 ELSE 0 END) AS Reenganchados_Activos
FROM ClientesActivos ca
JOIN ConteoPrestamosCliente cp ON cp.pr_id_cliente = ca.pr_id_cliente;


-- =========================================================================================
-- SECCION 4: TOP 10 EMPRESAS (COMPARATIVA: TODOS LOS CLIENTES vs SOLO CLIENTES ACTIVOS)
-- =========================================================================================
PRINT '>>> 4. TOP 10 EMPRESAS: CLIENTES TOTALES vs CLIENTES ACTIVOS';

;WITH ClientesActivos AS (
    SELECT DISTINCT pr_id_cliente
    FROM dbsolonegocios.dbo.tb_prestamos
    WHERE pr_estado = 1
)
SELECT TOP 10
    ISNULL(vc.EMPRESA, 'SIN EMPRESA') AS Empresa,
    COUNT(*) AS ClientesHistoricosTotal,
    SUM(CASE WHEN ca.pr_id_cliente IS NOT NULL THEN 1 ELSE 0 END) AS ClientesActivosActualmente
FROM dbsolonegocios.dbo.vw_datos_clientes vc
LEFT JOIN ClientesActivos ca ON ca.pr_id_cliente = vc.CODIGO
GROUP BY vc.EMPRESA
ORDER BY ClientesActivosActualmente DESC, ClientesHistoricosTotal DESC;


-- =========================================================================================
-- SECCION 5: ANALISIS DE ESTRUCTURA DE INTERESES Y MORAS
-- =========================================================================================
PRINT '>>> 5. ANALISIS DE NOTAS DE DEBITO (ND) DE INTERES Y MORA EN FINANCIERA';

SELECT 
    idTipoDocumento,
    idCxcTipo,
    COUNT(*) AS CantidadDocumentos,
    CAST(SUM(Valor) AS DECIMAL(18,2)) AS MontoTotal,
    SUM(CASE WHEN Referencia IS NOT NULL THEN 1 ELSE 0 END) AS ConReferenciaLlenada,
    SUM(CASE WHEN Referencia IS NULL THEN 1 ELSE 0 END) AS ConReferenciaNull,
    SUM(CASE WHEN Concepto LIKE '%PRESTAMO%' THEN 1 ELSE 0 END) AS ConPrestamoEnConcepto
FROM Financiera.dbo.Cxc
WHERE idTipoDocumento = 'ND'
GROUP BY idTipoDocumento, idCxcTipo;


-- =========================================================================================
-- SECCION 6: MUESTRA COMPARATIVA DE 3 PRESTAMOS ACTIVOS (SIN DATOS PERSONALES)
-- =========================================================================================
PRINT '>>> 6. MUESTRA COMPARATIVA DE PRESTAMOS: SOLONEGOCIOS vs FINANCIERA';

SELECT TOP 3
    p.pr_id_prestamos AS ID_Prestamo,
    CAST(p.pr_monto AS DECIMAL(18,2)) AS MontoCapital_SoloNegocios,
    CAST(p.pr_interes AS DECIMAL(18,2)) AS Interes_SoloNegocios,
    CAST(p.pr_balance AS DECIMAL(18,2)) AS Balance_SoloNegocios,
    p.pr_estado AS Estado_SoloNegocios,
    CAST(ISNULL(c.Valor, 0) AS DECIMAL(18,2)) AS ValorFT_Financiera,
    c.Cancelado AS Cancelado_Financiera,
    (SELECT COUNT(*) FROM Financiera.dbo.Cxc rc WHERE rc.idTipoDocumento = 'RC' AND rc.Concepto LIKE '%' + CAST(p.pr_id_prestamos AS VARCHAR(20)) + '%') AS CantRecibosEnFinanciera,
    (SELECT CAST(ISNULL(SUM(rc.Valor), 0) AS DECIMAL(18,2)) FROM Financiera.dbo.Cxc rc WHERE rc.idTipoDocumento = 'RC' AND rc.Concepto LIKE '%' + CAST(p.pr_id_prestamos AS VARCHAR(20)) + '%') AS TotalCobradoEnFinanciera
FROM dbsolonegocios.dbo.tb_prestamos p
LEFT JOIN Financiera.dbo.Cxc c ON (c.idDocumento = CAST(p.pr_id_prestamos AS VARCHAR(20)) OR c.Cxc = CAST(p.pr_id_prestamos AS VARCHAR(20))) AND c.idTipoDocumento = 'FT'
WHERE p.pr_estado = 1
ORDER BY p.pr_id_prestamos DESC;

PRINT '=========================================================================================';
PRINT '   FIN DEL REPORTE DE CONCILIACION';
PRINT '=========================================================================================';
