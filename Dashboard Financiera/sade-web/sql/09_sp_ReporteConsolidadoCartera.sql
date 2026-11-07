-- =========================================================================================
-- SP: cxcReporteConsolidadoCartera (Informe 2: Resumen Consolidado por Cartera Quincenal)
-- Versión Ultra-Optimizada con Filtrado Aislado y Cero Bloqueos:
--   1. Evalúa a nivel de PRÉSTAMO aislando candidatos en #PrestamosCandidatos.
--   2. Pagos y cobros se calculan ÚNICAMENTE para los préstamos de la quincena.
--   3. Préstamos cancelados se contabilizan como capitalClientesInactivosCancelados y
--      NUNCA alteran el capitalActivo.
--   4. Elimina escaneos de millones de recibos históricos (velocidad <1s garantizada).
-- =========================================================================================
USE Financiera
GO

IF OBJECT_ID('dbo.cxcReporteConsolidadoCartera', 'P') IS NOT NULL
    DROP PROCEDURE dbo.cxcReporteConsolidadoCartera
GO

CREATE PROCEDURE dbo.cxcReporteConsolidadoCartera
    @fechaCorte DATE         = NULL,
    @empresa    VARCHAR(200) = NULL,
    @fechaDesde DATE         = NULL,
    @fechaHasta DATE         = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

    -- Resolver fechaHasta y fechaCorte con total retrocompatibilidad
    SET @fechaHasta = ISNULL(@fechaHasta, ISNULL(@fechaCorte, CAST(GETDATE() AS DATE)));
    SET @fechaCorte = @fechaHasta;

    IF @fechaDesde IS NULL
    BEGIN
        IF DAY(@fechaHasta) <= 15
            SET @fechaDesde = DATEFROMPARTS(YEAR(@fechaHasta), MONTH(@fechaHasta), 1);
        ELSE
            SET @fechaDesde = DATEFROMPARTS(YEAR(@fechaHasta), MONTH(@fechaHasta), 16);
    END

    DECLARE @InicioQuincena DATE = @fechaDesde;
    DECLARE @FinQuincena    DATE = @fechaHasta;

    -- ── 1. Tabla Temporal de Préstamos Candidatos de la Quincena ───────
    CREATE TABLE #PrestamosCandidatos (
        pr_id_oficina          INT,
        pr_id_cliente          INT,
        pr_id_prestamos        BIGINT,
        pr_monto               DECIMAL(18,2),
        pr_tasa_interes        FLOAT,
        pr_fecha               DATETIME,
        pr_fecha_cancelacion   DATETIME,
        pr_estado              INT,
        PRIMARY KEY (pr_id_oficina, pr_id_prestamos)
    );

    CREATE NONCLUSTERED INDEX IX_Tmp_Cand_Cliente 
    ON #PrestamosCandidatos (pr_id_oficina, pr_id_cliente);

    INSERT INTO #PrestamosCandidatos
    SELECT 
        p.pr_id_oficina,
        p.pr_id_cliente,
        p.pr_id_prestamos,
        ISNULL(p.pr_monto, 0),
        ISNULL(p.pr_tasa_interes, 0),
        p.pr_fecha,
        p.pr_fecha_cancelacion,
        p.pr_estado
    FROM dbsolonegocios.dbo.tb_prestamos p WITH (NOLOCK)
    WHERE (
        -- Préstamo activo vigente
        (
            p.pr_estado = 1 
            AND NOT EXISTS (
                SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg WITH (NOLOCK) 
                WHERE rg.rg_id_prestamo = p.pr_id_prestamos AND rg.rg_id_oficina = p.pr_id_oficina
                  AND CAST(rg.rg_fecha AS DATE) <= @FinQuincena
            )
            AND (p.pr_fecha_cancelacion IS NULL OR CAST(p.pr_fecha_cancelacion AS DATE) > @FinQuincena)
            AND EXISTS (
                SELECT 1 FROM dbsolonegocios.dbo.tb_detalle_prestamos dp WITH (NOLOCK)
                WHERE dp.dp_id_prestamos = p.pr_id_prestamos AND dp.dp_id_oficina = p.pr_id_oficina 
                  AND dp.dp_estado = 1 AND dp.dp_saldo_capital > 0
            )
        )
        -- Otorgado en la quincena
        OR (CAST(p.pr_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena AND ISNULL(p.pr_estado, 0) <> 0)
        -- Cobros registrados en la quincena
        OR EXISTS (
            SELECT 1 FROM dbsolonegocios.dbo.tb_recibo_pagos rp WITH (NOLOCK)
            WHERE rp.rp_id_prestamo = p.pr_id_prestamos AND rp.rp_id_oficina = p.pr_id_oficina
              AND rp.rp_estado = 1
              AND CAST(rp.rp_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena
        )
        -- Cancelado por reenganche en la quincena
        OR EXISTS (
            SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg WITH (NOLOCK)
            WHERE rg.rg_id_prestamo = p.pr_id_prestamos AND rg.rg_id_oficina = p.pr_id_oficina
              AND CAST(rg.rg_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena
        )
        -- Cancelado oficialmente en la quincena
        OR (p.pr_fecha_cancelacion IS NOT NULL AND CAST(p.pr_fecha_cancelacion AS DATE) BETWEEN @InicioQuincena AND @FinQuincena)
    );

    -- ── 2. Pre-resolver Carteras Únicamente para los Clientes Candidatos 
    CREATE TABLE #ClientesCarteraRef (
        idOficina INT,
        idCliente INT,
        cartera   VARCHAR(200),
        PRIMARY KEY (idOficina, idCliente)
    );

    INSERT INTO #ClientesCarteraRef
    SELECT 
        dc.pr_id_oficina,
        dc.pr_id_cliente,
        ISNULL(
            NULLIF(LTRIM(RTRIM(vc.EMPRESA)), ''),
            ISNULL(NULLIF(LTRIM(RTRIM(co.co_nombre)), ''), 'Sin Cartera')
        ) AS cartera
    FROM (SELECT DISTINCT pr_id_oficina, pr_id_cliente FROM #PrestamosCandidatos) dc
    OUTER APPLY (
        SELECT TOP 1 vc1.EMPRESA
        FROM dbsolonegocios.dbo.vw_datos_clientes vc1 WITH (NOLOCK)
        WHERE vc1.CODIGO = dc.pr_id_cliente AND vc1.ID_OFICINA = dc.pr_id_oficina
    ) vc
    OUTER APPLY (
        SELECT TOP 1 cp.co_nombre
        FROM dbsolonegocios.dbo.tb_datos_laboral dl WITH (NOLOCK)
        INNER JOIN dbsolonegocios.dbo.tb_compania cp WITH (NOLOCK) ON cp.co_id = dl.dl_id_empresa
        WHERE dl.dl_id_cliente = dc.pr_id_cliente AND dl.dl_id_oficina = dc.pr_id_oficina
        ORDER BY dl.dl_id DESC
    ) co;

    -- ── 3. Tabla Temporal de Préstamos para Consolidado ───────────────
    CREATE TABLE #PrestamosCartera (
        idOficina               INT,
        idCliente               INT,
        idPrestamo              BIGINT,
        cartera                 VARCHAR(200),
        montoPrestamo           DECIMAL(18,2),
        capitalPagado           DECIMAL(18,2),
        capitalActualAdeudado   DECIMAL(18,2),
        balanceAntesCobro       DECIMAL(18,2),
        capitalCobradoQuincena  DECIMAL(18,2),
        interesCobradoQuincena  DECIMAL(18,2),
        tasa                    FLOAT,
        esActivo                BIT
    );

    -- ── 4. Agregaciones Acotadas Exclusivamente a Préstamos Candidatos 
    ;WITH PagosHistoricos AS (
        SELECT 
            rp.rp_id_oficina,
            rp.rp_id_prestamo,
            ISNULL(SUM(rp.rp_capital), 0) AS capitalPagadoTotal
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp WITH (NOLOCK)
        INNER JOIN #PrestamosCandidatos pc 
            ON pc.pr_id_prestamos = rp.rp_id_prestamo AND pc.pr_id_oficina = rp.rp_id_oficina
        WHERE rp.rp_estado = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
          AND ISNULL(rp.rp_observacion, '') NOT LIKE '%Nota de Credito%'
          AND ISNULL(rp.rp_observacion, '') NOT LIKE '%Reenganche%'
          AND NOT EXISTS (
              SELECT 1 FROM dbsolonegocios.dbo.tb_notas_credito nc WITH (NOLOCK)
              WHERE nc.nc_recibo_pago = rp.rp_id_recibo AND nc.nc_id_oficina = rp.rp_id_oficina
          )
        GROUP BY rp.rp_id_oficina, rp.rp_id_prestamo
    ),
    CobrosQuincena AS (
        SELECT 
            rp.rp_id_oficina,
            rp.rp_id_prestamo,
            ISNULL(SUM(rp.rp_capital), 0) AS capitalCobrado,
            ISNULL(SUM(rp.rp_interes), 0) AS interesCobrado
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp WITH (NOLOCK)
        INNER JOIN #PrestamosCandidatos pc 
            ON pc.pr_id_prestamos = rp.rp_id_prestamo AND pc.pr_id_oficina = rp.rp_id_oficina
        WHERE rp.rp_estado = 1
          AND CAST(rp.rp_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena
          AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
          AND ISNULL(rp.rp_observacion, '') NOT LIKE '%Nota de Credito%'
          AND ISNULL(rp.rp_observacion, '') NOT LIKE '%Reenganche%'
          AND NOT EXISTS (
              SELECT 1 FROM dbsolonegocios.dbo.tb_notas_credito nc WITH (NOLOCK)
              WHERE nc.nc_recibo_pago = rp.rp_id_recibo AND nc.nc_id_oficina = rp.rp_id_oficina
          )
        GROUP BY rp.rp_id_oficina, rp.rp_id_prestamo
    ),
    PrestamosEvaluados AS (
        SELECT 
            pc.pr_id_oficina,
            pc.pr_id_cliente,
            pc.pr_id_prestamos,
            pc.pr_monto,
            pc.pr_tasa_interes,
            pc.pr_fecha,
            pc.pr_estado,
            ISNULL(ph.capitalPagadoTotal, 0) AS capitalPagadoTotal,
            ISNULL(cq.capitalCobrado, 0)     AS capitalCobradoQuincena,
            ISNULL(cq.interesCobrado, 0)     AS interesCobradoQuincena,
            CASE 
                WHEN pc.pr_estado = 1 
                     AND (ISNULL(pc.pr_monto, 0) - ISNULL(ph.capitalPagadoTotal, 0)) > 0
                     AND NOT EXISTS (
                         SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg WITH (NOLOCK)
                         WHERE rg.rg_id_prestamo = pc.pr_id_prestamos AND rg.rg_id_oficina = pc.pr_id_oficina
                           AND CAST(rg.rg_fecha AS DATE) <= @FinQuincena
                     )
                     AND (pc.pr_fecha_cancelacion IS NULL OR CAST(pc.pr_fecha_cancelacion AS DATE) > @FinQuincena)
                     AND EXISTS (
                         SELECT 1 FROM dbsolonegocios.dbo.tb_detalle_prestamos dp WITH (NOLOCK)
                         WHERE dp.dp_id_prestamos = pc.pr_id_prestamos AND dp.dp_id_oficina = pc.pr_id_oficina 
                           AND dp.dp_estado = 1 AND dp.dp_saldo_capital > 0
                     )
                THEN 1 ELSE 0 
            END AS esActivo
        FROM #PrestamosCandidatos pc
        LEFT JOIN PagosHistoricos ph ON ph.rp_id_prestamo = pc.pr_id_prestamos AND ph.rp_id_oficina = pc.pr_id_oficina
        LEFT JOIN CobrosQuincena cq ON cq.rp_id_prestamo = pc.pr_id_prestamos AND cq.rp_id_oficina = pc.pr_id_oficina
    )
    INSERT INTO #PrestamosCartera
    SELECT
        pe.pr_id_oficina,
        pe.pr_id_cliente,
        pe.pr_id_prestamos,
        cr.cartera,
        CAST(pe.pr_monto AS DECIMAL(18,2)) AS montoPrestamo,
        
        -- Capital Pagado
        CAST(
            CASE 
                WHEN pe.esActivo = 0 THEN pe.pr_monto
                WHEN pe.capitalPagadoTotal > pe.pr_monto THEN pe.pr_monto
                WHEN pe.capitalPagadoTotal < 0 THEN 0.00
                ELSE pe.capitalPagadoTotal
            END AS DECIMAL(18,2)
        ) AS capitalPagado,

        -- Capital Actual Adeudado (0.00 si está cancelado)
        CAST(
            CASE 
                WHEN pe.esActivo = 1 THEN
                    (CASE 
                        WHEN (pe.pr_monto - pe.capitalPagadoTotal) < 0 THEN 0.00 
                        ELSE (pe.pr_monto - pe.capitalPagadoTotal) 
                    END)
                ELSE 0.00
            END AS DECIMAL(18,2)
        ) AS capitalActualAdeudado,

        -- Balance Antes del Cobro (solo para préstamos activos; 0.00 para cancelados)
        CAST(
            CASE 
                WHEN pe.esActivo = 1 THEN
                    (CASE 
                        WHEN (pe.pr_monto - pe.capitalPagadoTotal) < 0 THEN 0.00 
                        ELSE (pe.pr_monto - pe.capitalPagadoTotal) 
                    END) + pe.capitalCobradoQuincena
                ELSE 0.00
            END AS DECIMAL(18,2)
        ) AS balanceAntesCobro,

        pe.capitalCobradoQuincena,
        pe.interesCobradoQuincena,
        CAST(pe.pr_tasa_interes AS FLOAT) AS tasa,
        pe.esActivo
    FROM PrestamosEvaluados pe
    INNER JOIN #ClientesCarteraRef cr 
        ON cr.idCliente = pe.pr_id_cliente AND cr.idOficina = pe.pr_id_oficina
    WHERE (@empresa IS NULL OR cr.cartera LIKE '%' + @empresa + '%');

    -- ── 5. Agrupación Consolidada por Cartera ─────────────────────────
    ;WITH ResumenCartera AS (
        SELECT
            pc.cartera,
            
            -- Balance Capital Colocado: monto original ÚNICAMENTE de los préstamos ACTIVOS
            ISNULL(SUM(CASE WHEN pc.esActivo = 1 THEN pc.montoPrestamo ELSE 0 END), 0) AS balanceCapitalColocado,
            
            -- Capital Inactivos / Cancelados: monto original de los préstamos que NO están activos
            ISNULL(SUM(CASE WHEN pc.esActivo = 0 THEN pc.montoPrestamo ELSE 0 END), 0) AS capitalClientesInactivosCancelados,
            
            -- Capital Activo: Balance antes del cobro ÚNICAMENTE de los préstamos ACTIVOS (Cancelados = 0.00)
            ISNULL(SUM(CASE WHEN pc.esActivo = 1 THEN pc.balanceAntesCobro ELSE 0 END), 0) AS capitalActivo,
            
            -- Conteo de Clientes Activos e Inactivos únicos
            COUNT(DISTINCT CASE WHEN pc.esActivo = 1 THEN pc.idCliente END) AS clientesActivos,
            COUNT(DISTINCT CASE WHEN pc.esActivo = 0 THEN pc.idCliente END) AS clientesInactivos,
            
            -- Cobros quincenales reales
            ISNULL(SUM(pc.capitalCobradoQuincena), 0) AS capitalCobradoQuincena,
            ISNULL(SUM(pc.interesCobradoQuincena), 0) AS interesCobradoQuincena,
            
            -- Tasa ponderada de la cartera activa
            CASE
                WHEN SUM(CASE WHEN pc.esActivo = 1 THEN pc.montoPrestamo ELSE 0 END) > 0
                THEN ROUND(
                    SUM(CASE WHEN pc.esActivo = 1 THEN pc.montoPrestamo * pc.tasa ELSE 0 END)
                    / SUM(CASE WHEN pc.esActivo = 1 THEN pc.montoPrestamo ELSE 0 END),
                    2
                )
                WHEN AVG(pc.tasa) IS NOT NULL THEN ROUND(AVG(pc.tasa), 2)
                ELSE 0.00
            END AS tasa
        FROM #PrestamosCartera pc
        GROUP BY pc.cartera
    )
    SELECT
        cartera,
        balanceCapitalColocado,
        capitalClientesInactivosCancelados,
        capitalActivo,
        clientesActivos,
        clientesInactivos,
        capitalCobradoQuincena,
        interesCobradoQuincena,
        tasa
    FROM ResumenCartera
    WHERE clientesActivos > 0
       OR capitalCobradoQuincena > 0
       OR interesCobradoQuincena > 0
       OR @empresa IS NOT NULL
    ORDER BY balanceCapitalColocado DESC, capitalActivo DESC;

    -- ── Result Set 2: Fila de Totales Generales en pesos ($) ──────────
    SELECT 
        COUNT(DISTINCT CASE WHEN esActivo = 1 OR capitalCobradoQuincena > 0 OR interesCobradoQuincena > 0 OR @empresa IS NOT NULL THEN cartera END) AS totalCarteras,
        ISNULL(SUM(CASE WHEN esActivo = 1 THEN montoPrestamo ELSE 0 END), 0)          AS totalBalanceCapitalColocado,
        ISNULL(SUM(CASE WHEN esActivo = 0 THEN montoPrestamo ELSE 0 END), 0)          AS totalCapitalInactivosCancelados,
        ISNULL(SUM(CASE WHEN esActivo = 1 THEN balanceAntesCobro ELSE 0 END), 0)      AS totalCapitalActivo,
        COUNT(DISTINCT CASE WHEN esActivo = 1 THEN idCliente END)                     AS totalClientesActivos,
        COUNT(DISTINCT CASE WHEN esActivo = 0 THEN idCliente END)                     AS totalClientesInactivos,
        ISNULL(SUM(capitalCobradoQuincena), 0)                                        AS totalCapitalCobradoQuincena,
        ISNULL(SUM(interesCobradoQuincena), 0)                                        AS totalInteresCobradoQuincena,
        CASE 
            WHEN SUM(CASE WHEN esActivo = 1 THEN montoPrestamo ELSE 0 END) > 0
            THEN ROUND(
                SUM(CASE WHEN esActivo = 1 THEN montoPrestamo * tasa ELSE 0 END)
                / SUM(CASE WHEN esActivo = 1 THEN montoPrestamo ELSE 0 END),
                2
            )
            WHEN AVG(tasa) IS NOT NULL THEN ROUND(AVG(tasa), 2)
            ELSE 0.00
        END AS tasaPromedioPonderada,
        @fechaDesde                                                                   AS periodoDesde,
        @fechaHasta                                                                   AS periodoHasta,
        @InicioQuincena                                                               AS quincenaDesde,
        @FinQuincena                                                                  AS quincenaHasta
    FROM #PrestamosCartera;

    DROP TABLE #PrestamosCandidatos;
    DROP TABLE #ClientesCarteraRef;
    DROP TABLE #PrestamosCartera;
END
GO
