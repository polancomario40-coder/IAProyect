-- =========================================================================================
-- SP: cxcReporteClientesAtrasados (Reporte Especializado de Clientes en Mora por Tramos y Compañía)
-- Tramos Oficiales Solicitados:
--   1. 30 días (1 a 30 días de atraso)
--   2. Legal 60 días (31 a 60 días de atraso)
--   3. 90 días o más (más de 60 días de atraso / mora crítica)
--
-- Devuelve:
--   Result Set 1: Resumen de Cartera agrupado por Compañía / Empresa
--   Result Set 2: Detalle individual de Clientes y Préstamos en Mora
--   Result Set 3: Fila de Totales Generales de la Cartera en Mora
-- =========================================================================================
USE Financiera
GO

IF OBJECT_ID('dbo.cxcReporteClientesAtrasados', 'P') IS NOT NULL
    DROP PROCEDURE dbo.cxcReporteClientesAtrasados
GO

CREATE PROCEDURE dbo.cxcReporteClientesAtrasados
    @fechaCorte  DATE         = NULL,
    @empresa     VARCHAR(200) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

    -- Si no se especifica fecha de corte, usar la fecha actual del sistema
    SET @fechaCorte = ISNULL(@fechaCorte, CAST(GETDATE() AS DATE));

    -- ── 1. Extraer Préstamos Activos con Cuotas Vencidas Impagas ───────
    CREATE TABLE #PrestamosMora (
        pr_id_oficina          INT,
        pr_id_cliente          INT,
        pr_id_prestamos        BIGINT,
        pr_monto               DECIMAL(18,2),
        pr_tasa_interes        FLOAT,
        saldoCapitalTotal      DECIMAL(18,2),
        capitalVencido         DECIMAL(18,2),
        interesVencido         DECIMAL(18,2),
        moraPendiente          DECIMAL(18,2),
        cuotasVencidas         INT,
        primeraFechaVenc       DATE,
        diasAtraso             INT,
        tramoMora              VARCHAR(30),
        PRIMARY KEY (pr_id_oficina, pr_id_prestamos)
    );

    CREATE NONCLUSTERED INDEX IX_Tmp_Mora_Cli 
    ON #PrestamosMora (pr_id_oficina, pr_id_cliente);

    ;WITH CuotasVencidasAgrupadas AS (
        SELECT 
            dp.dp_id_oficina,
            dp.dp_id_prestamos,
            SUM(ISNULL(dp.dp_saldo_capital, 0)) AS saldoCapitalTotal,
            SUM(CASE WHEN CAST(dp.dp_fecha_venc AS DATE) < @fechaCorte THEN ISNULL(dp.dp_saldo_capital, 0) ELSE 0 END) AS capitalVencido,
            SUM(CASE WHEN CAST(dp.dp_fecha_venc AS DATE) < @fechaCorte THEN ISNULL(dp.dp_saldo_interes, 0) ELSE 0 END) AS interesVencido,
            SUM(CASE WHEN CAST(dp.dp_fecha_venc AS DATE) < @fechaCorte THEN ISNULL(dp.dp_saldo_mora, 0) ELSE 0 END) AS moraPendiente,
            COUNT(CASE WHEN CAST(dp.dp_fecha_venc AS DATE) < @fechaCorte AND (ISNULL(dp.dp_saldo_capital, 0) + ISNULL(dp.dp_saldo_interes, 0)) > 0 THEN 1 END) AS cuotasVencidas,
            MIN(CASE WHEN CAST(dp.dp_fecha_venc AS DATE) < @fechaCorte AND (ISNULL(dp.dp_saldo_capital, 0) + ISNULL(dp.dp_saldo_interes, 0)) > 0 THEN CAST(dp.dp_fecha_venc AS DATE) END) AS primeraFechaVenc
        FROM dbsolonegocios.dbo.tb_detalle_prestamos dp WITH (NOLOCK)
        WHERE dp.dp_estado = 1
        GROUP BY dp.dp_id_oficina, dp.dp_id_prestamos
        HAVING COUNT(CASE WHEN CAST(dp.dp_fecha_venc AS DATE) < @fechaCorte AND (ISNULL(dp.dp_saldo_capital, 0) + ISNULL(dp.dp_saldo_interes, 0)) > 0 THEN 1 END) > 0
    )
    INSERT INTO #PrestamosMora
    SELECT 
        p.pr_id_oficina,
        p.pr_id_cliente,
        p.pr_id_prestamos,
        ISNULL(p.pr_monto, 0),
        ISNULL(p.pr_tasa_interes, 0),
        cv.saldoCapitalTotal,
        cv.capitalVencido,
        cv.interesVencido,
        cv.moraPendiente,
        cv.cuotasVencidas,
        cv.primeraFechaVenc,
        DATEDIFF(day, cv.primeraFechaVenc, @fechaCorte) AS diasAtraso,
        CASE 
            WHEN DATEDIFF(day, cv.primeraFechaVenc, @fechaCorte) <= 30 THEN '30 DIAS'
            WHEN DATEDIFF(day, cv.primeraFechaVenc, @fechaCorte) <= 60 THEN 'LEGAL 60 DIAS'
            ELSE '90+ DIAS'
        END AS tramoMora
    FROM dbsolonegocios.dbo.tb_prestamos p WITH (NOLOCK)
    INNER JOIN CuotasVencidasAgrupadas cv 
        ON cv.dp_id_prestamos = p.pr_id_prestamos AND cv.dp_id_oficina = p.pr_id_oficina
    WHERE p.pr_estado = 1
      AND (p.pr_fecha_cancelacion IS NULL OR CAST(p.pr_fecha_cancelacion AS DATE) > @fechaCorte);

    -- ── 2. Resolver Información de Clientes ────────────────────────────
    CREATE TABLE #ClientesMoraInfo (
        idOficina     INT,
        idCliente     INT,
        nombreCliente VARCHAR(200),
        cedula        VARCHAR(30),
        telefono      VARCHAR(50),
        empresa       VARCHAR(200),
        PRIMARY KEY (idOficina, idCliente)
    );

    INSERT INTO #ClientesMoraInfo
    SELECT 
        dm.pr_id_oficina,
        dm.pr_id_cliente,
        ISNULL(
            NULLIF(LTRIM(RTRIM(vc.NOMBRE_COMPLETO)), ''),
            ISNULL(NULLIF(LTRIM(RTRIM(ISNULL(c.cl_nombre, '') + ' ' + ISNULL(c.cl_apellido, ''))), ''), 'CLIENTE #' + CAST(dm.pr_id_cliente AS VARCHAR(20)))
        ) AS nombreCliente,
        ISNULL(vc.IDENTIDAD, c.cl_identidad) AS cedula,
        COALESCE(NULLIF(vc.CELULAR, ''), NULLIF(vc.TELEFONO_RESIDENCIA, ''), NULLIF(c.cl_celular, ''), c.cl_telefono_resd, '') AS telefono,
        ISNULL(
            NULLIF(LTRIM(RTRIM(vc.EMPRESA)), ''),
            ISNULL(NULLIF(LTRIM(RTRIM(co.co_nombre)), ''), 'Sin Cartera')
        ) AS empresa
    FROM (SELECT DISTINCT pr_id_oficina, pr_id_cliente FROM #PrestamosMora) dm
    LEFT JOIN dbsolonegocios.dbo.tb_clientes c WITH (NOLOCK)
        ON c.cl_id_cliente = dm.pr_id_cliente AND c.cl_id_oficina = dm.pr_id_oficina
    OUTER APPLY (
        SELECT TOP 1 vc1.NOMBRE_COMPLETO, vc1.IDENTIDAD, vc1.EMPRESA, vc1.CELULAR, vc1.TELEFONO_RESIDENCIA
        FROM dbsolonegocios.dbo.vw_datos_clientes vc1 WITH (NOLOCK)
        WHERE vc1.CODIGO = dm.pr_id_cliente AND vc1.ID_OFICINA = dm.pr_id_oficina
    ) vc
    OUTER APPLY (
        SELECT TOP 1 cp.co_nombre
        FROM dbsolonegocios.dbo.tb_datos_laboral dl WITH (NOLOCK)
        INNER JOIN dbsolonegocios.dbo.tb_compania cp WITH (NOLOCK) ON cp.co_id = dl.dl_id_empresa
        WHERE dl.dl_id_cliente = dm.pr_id_cliente AND dl.dl_id_oficina = dm.pr_id_oficina
        ORDER BY dl.dl_id DESC
    ) co;

    -- ── 3. Tabla Unificada de Detalle de Mora ──────────────────────────
    CREATE TABLE #DetalleMoraCompleto (
        idOficina          INT,
        idCliente          INT,
        nombreCliente      VARCHAR(200),
        cedula             VARCHAR(30),
        telefono           VARCHAR(50),
        empresa            VARCHAR(200),
        numeroPrestamo     VARCHAR(50),
        montoOriginal      DECIMAL(18,2),
        tasa               FLOAT,
        saldoCapital       DECIMAL(18,2),
        capitalVencido     DECIMAL(18,2),
        interesVencido     DECIMAL(18,2),
        moraPendiente      DECIMAL(18,2),
        totalVencido       DECIMAL(18,2),
        cuotasVencidas     INT,
        primeraFechaVenc   DATE,
        diasAtraso         INT,
        tramoMora          VARCHAR(30)
    );

    INSERT INTO #DetalleMoraCompleto
    SELECT 
        pm.pr_id_oficina,
        pm.pr_id_cliente,
        cmi.nombreCliente,
        cmi.cedula,
        cmi.telefono,
        cmi.empresa,
        CAST(pm.pr_id_prestamos AS VARCHAR(50)) AS numeroPrestamo,
        pm.pr_monto                             AS montoOriginal,
        pm.pr_tasa_interes                      AS tasa,
        pm.saldoCapitalTotal                    AS saldoCapital,
        pm.capitalVencido,
        pm.interesVencido,
        pm.moraPendiente,
        (pm.capitalVencido + pm.interesVencido + pm.moraPendiente) AS totalVencido,
        pm.cuotasVencidas,
        pm.primeraFechaVenc,
        pm.diasAtraso,
        pm.tramoMora
    FROM #PrestamosMora pm
    INNER JOIN #ClientesMoraInfo cmi 
        ON cmi.idCliente = pm.pr_id_cliente AND cmi.idOficina = pm.pr_id_oficina;

    -- Filtrar por empresa si fue especificado
    IF @empresa IS NOT NULL AND RTRIM(LTRIM(@empresa)) <> ''
        DELETE FROM #DetalleMoraCompleto WHERE empresa NOT LIKE '%' + @empresa + '%';

    -- ── RESULT SET 1: Resumen por Compañía / Cartera ───────────────────
    SELECT 
        empresa                                                             AS cartera,
        COUNT(DISTINCT idCliente)                                           AS totalClientesMora,
        COUNT(DISTINCT numeroPrestamo)                                      AS totalPrestamosMora,
        CAST(SUM(CASE WHEN tramoMora = '30 DIAS' THEN capitalVencido ELSE 0 END) AS DECIMAL(18,2)) AS capitalMora30Dias,
        CAST(SUM(CASE WHEN tramoMora = 'LEGAL 60 DIAS' THEN capitalVencido ELSE 0 END) AS DECIMAL(18,2)) AS capitalMora60DiasLegal,
        CAST(SUM(CASE WHEN tramoMora = '90+ DIAS' THEN capitalVencido ELSE 0 END) AS DECIMAL(18,2)) AS capitalMora90MasDias,
        CAST(SUM(capitalVencido) AS DECIMAL(18,2))                          AS totalCapitalMora,
        CAST(SUM(interesVencido + moraPendiente) AS DECIMAL(18,2))          AS otrosCargosMora,
        CAST(SUM(totalVencido) AS DECIMAL(18,2))                            AS totalDeudaMora
    FROM #DetalleMoraCompleto
    GROUP BY empresa
    ORDER BY totalCapitalMora DESC, empresa ASC;

    -- ── RESULT SET 2: Detalle Individual de Clientes en Mora ──────────
    SELECT 
        idCliente,
        nombreCliente,
        cedula,
        telefono,
        empresa,
        numeroPrestamo,
        montoOriginal,
        tasa,
        saldoCapital,
        capitalVencido,
        interesVencido,
        moraPendiente,
        totalVencido,
        cuotasVencidas,
        primeraFechaVenc,
        diasAtraso,
        tramoMora
    FROM #DetalleMoraCompleto
    ORDER BY diasAtraso DESC, capitalVencido DESC;

    -- ── RESULT SET 3: Totales Generales de la Cartera en Mora ─────────
    SELECT 
        COUNT(DISTINCT empresa)                                             AS totalCarteras,
        COUNT(DISTINCT idCliente)                                           AS totalClientesMora,
        COUNT(DISTINCT numeroPrestamo)                                      AS totalPrestamosMora,
        CAST(ISNULL(SUM(CASE WHEN tramoMora = '30 DIAS' THEN capitalVencido ELSE 0 END), 0) AS DECIMAL(18,2)) AS totalCapitalMora30Dias,
        CAST(ISNULL(SUM(CASE WHEN tramoMora = 'LEGAL 60 DIAS' THEN capitalVencido ELSE 0 END), 0) AS DECIMAL(18,2)) AS totalCapitalMora60DiasLegal,
        CAST(ISNULL(SUM(CASE WHEN tramoMora = '90+ DIAS' THEN capitalVencido ELSE 0 END), 0) AS DECIMAL(18,2)) AS totalCapitalMora90MasDias,
        CAST(ISNULL(SUM(capitalVencido), 0) AS DECIMAL(18,2))               AS totalCapitalMora,
        CAST(ISNULL(SUM(interesVencido), 0) AS DECIMAL(18,2))               AS totalInteresVencido,
        CAST(ISNULL(SUM(moraPendiente), 0) AS DECIMAL(18,2))                AS totalMoraPendiente,
        CAST(ISNULL(SUM(totalVencido), 0) AS DECIMAL(18,2))                 AS totalDeudaMora,
        @fechaCorte                                                         AS fechaCorte
    FROM #DetalleMoraCompleto;

    -- Limpieza de tablas temporales
    DROP TABLE #PrestamosMora;
    DROP TABLE #ClientesMoraInfo;
    DROP TABLE #DetalleMoraCompleto;
END;
GO
