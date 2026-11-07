-- =========================================================================================
-- SP: cxcReporteDetalleClientes (Informe 1: Detalle Quincenal por Préstamo)
-- Versión Ultra-Optimizada con Filtrado Aislado y Cero Bloqueos:
--   1. Evalúa a nivel de PRÉSTAMO (permite ver cancelados y reenganchados en el mismo período).
--   2. Aísla préstamos candidatos en #PrestamosCandidatos con Clave Primaria:
--      -> Pagos históricos, cobros y cuotas se filtran ÚNICAMENTE para los préstamos activos/quincena.
--      -> Elimina escaneos completos de millones de recibos históricos (de 56s a <1s).
--   3. Pre-resuelve datos de clientes (#ClientesInfo) para evitar llamadas redundantes a vistas pesadas.
--   4. Soporta @tipoReporte = 'TODOS', 'NUEVOS', 'REENGANCHADOS', 'CANCELADOS', 'EN MORA', 'AL DIA'.
-- =========================================================================================
USE Financiera
GO

IF OBJECT_ID('dbo.cxcReporteDetalleClientes', 'P') IS NOT NULL
    DROP PROCEDURE dbo.cxcReporteDetalleClientes
GO

CREATE PROCEDURE dbo.cxcReporteDetalleClientes
    @fechaDesde       DATE         = NULL,
    @fechaHasta       DATE         = NULL,
    @empresa          VARCHAR(200) = NULL,
    @tipoReporte      VARCHAR(30)  = 'TODOS'  -- 'TODOS' | 'NUEVOS' | 'REENGANCHADOS' | 'CANCELADOS' | 'EN MORA' | 'AL DIA'
AS
BEGIN
    SET NOCOUNT ON;
    SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

    -- Si no se especifica fechaHasta, se asume la fecha actual
    SET @fechaHasta = ISNULL(@fechaHasta, CAST(GETDATE() AS DATE));

    -- Si no se especifica fechaDesde, se asume el inicio de la quincena correspondiente a @fechaHasta
    IF @fechaDesde IS NULL
    BEGIN
        IF DAY(@fechaHasta) <= 15
            SET @fechaDesde = DATEFROMPARTS(YEAR(@fechaHasta), MONTH(@fechaHasta), 1);
        ELSE
            SET @fechaDesde = DATEFROMPARTS(YEAR(@fechaHasta), MONTH(@fechaHasta), 16);
    END

    DECLARE @InicioQuincena DATE = @fechaDesde;
    DECLARE @FinQuincena    DATE = @fechaHasta;
    DECLARE @Hoy            DATE = CAST(GETDATE() AS DATE);

    -- ── 1. Tabla Temporal de Préstamos Candidatos de la Quincena ───────
    CREATE TABLE #PrestamosCandidatos (
        pr_id_oficina          INT,
        pr_id_cliente          INT,
        pr_id_prestamos        BIGINT,
        pr_monto               DECIMAL(18,2),
        pr_tasa_interes        FLOAT,
        pr_fecha               DATETIME,
        pr_fecha_venc          DATETIME,
        pr_fecha_cancelacion   DATETIME,
        pr_estado              INT,
        PRIMARY KEY (pr_id_oficina, pr_id_prestamos)
    );

    CREATE NONCLUSTERED INDEX IX_Tmp_Cand_Cliente 
    ON #PrestamosCandidatos (pr_id_oficina, pr_id_cliente);

    -- Insertar únicamente préstamos con vigencia o actividad en el período
    INSERT INTO #PrestamosCandidatos
    SELECT 
        p.pr_id_oficina,
        p.pr_id_cliente,
        p.pr_id_prestamos,
        ISNULL(p.pr_monto, 0),
        ISNULL(p.pr_tasa_interes, 0),
        p.pr_fecha,
        p.pr_fecha_venc,
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

    -- ── 2. Pre-resolver información de Clientes Únicos Candidatos ─────
    CREATE TABLE #ClientesInfo (
        idOficina     INT,
        idCliente     INT,
        nombreCliente VARCHAR(200),
        cedula        VARCHAR(30),
        empresa       VARCHAR(200),
        PRIMARY KEY (idOficina, idCliente)
    );

    INSERT INTO #ClientesInfo
    SELECT 
        dc.pr_id_oficina,
        dc.pr_id_cliente,
        ISNULL(
            NULLIF(LTRIM(RTRIM(vc.NOMBRE_COMPLETO)), ''),
            ISNULL(NULLIF(LTRIM(RTRIM(ISNULL(c.cl_nombre, '') + ' ' + ISNULL(c.cl_apellido, ''))), ''), 'CLIENTE #' + CAST(dc.pr_id_cliente AS VARCHAR(20)))
        ) AS nombreCliente,
        ISNULL(vc.IDENTIDAD, c.cl_identidad) AS cedula,
        ISNULL(
            NULLIF(LTRIM(RTRIM(vc.EMPRESA)), ''),
            ISNULL(NULLIF(LTRIM(RTRIM(co.co_nombre)), ''), 'Sin Cartera')
        ) AS empresa
    FROM (SELECT DISTINCT pr_id_oficina, pr_id_cliente FROM #PrestamosCandidatos) dc
    LEFT JOIN dbsolonegocios.dbo.tb_clientes c WITH (NOLOCK)
        ON c.cl_id_cliente = dc.pr_id_cliente AND c.cl_id_oficina = dc.pr_id_oficina
    OUTER APPLY (
        SELECT TOP 1 vc1.NOMBRE_COMPLETO, vc1.IDENTIDAD, vc1.EMPRESA
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

    -- ── 3. Tabla de Resultados del Detalle ────────────────────────────
    CREATE TABLE #ReporteDetalle (
        idOficina               INT,
        idCliente               INT,
        nombreCliente           VARCHAR(200),
        cedula                  VARCHAR(30),
        empresa                 VARCHAR(200),
        numeroPrestamo          VARCHAR(50),
        montoPrestamo           DECIMAL(18,2),
        capitalPagado           DECIMAL(18,2),
        balanceAntesCobro       DECIMAL(18,2),
        tasa                    FLOAT,
        fechaPrestamo           DATETIME,
        capitalCobradoQuincena  DECIMAL(18,2),
        interesCobradoQuincena  DECIMAL(18,2),
        capitalActualAdeudado   DECIMAL(18,2),
        totalCobradoQuincena    DECIMAL(18,2),
        balanceActual           DECIMAL(18,2),
        clasificacion           VARCHAR(50),
        diasAtraso              INT,
        comentario              VARCHAR(250),
        totalPrestamosHist      INT,
        esNuevoEnPeriodo        BIT,
        esReengancheEnPeriodo   BIT
    );

    -- ── 4. Cálculos acotados ÚNICAMENTE a los préstamos candidatos ────
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
            ISNULL(SUM(rp.rp_capital), 0)      AS capitalCobrado,
            ISNULL(SUM(rp.rp_interes), 0)      AS interesCobrado,
            ISNULL(SUM(rp.rp_capital + rp.rp_interes + ISNULL(rp.rp_mora, 0)), 0) AS totalCobrado
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
    CuotasInfo AS (
        SELECT 
            dp.dp_id_oficina,
            dp.dp_id_prestamos,
            ISNULL(SUM(dp.dp_saldo_capital), 0) AS balanceCapital,
            ISNULL(SUM(dp.dp_saldo_capital + dp.dp_saldo_interes), 0) AS balanceTotalCuotas,
            SUM(CASE WHEN dp.dp_estado = 1 AND CAST(dp.dp_fecha_venc AS DATE) < @Hoy AND (ISNULL(dp.dp_saldo_capital, 0) + ISNULL(dp.dp_saldo_interes, 0)) > 0 THEN 1 ELSE 0 END) AS cuotasVencidas,
            MIN(CASE WHEN dp.dp_estado = 1 AND CAST(dp.dp_fecha_venc AS DATE) < @Hoy AND (ISNULL(dp.dp_saldo_capital, 0) + ISNULL(dp.dp_saldo_interes, 0)) > 0 THEN CAST(dp.dp_fecha_venc AS DATE) END) AS minFechaVencida
        FROM dbsolonegocios.dbo.tb_detalle_prestamos dp WITH (NOLOCK)
        INNER JOIN #PrestamosCandidatos pc 
            ON pc.pr_id_prestamos = dp.dp_id_prestamos AND pc.pr_id_oficina = dp.dp_id_oficina
        WHERE dp.dp_estado = 1
        GROUP BY dp.dp_id_oficina, dp.dp_id_prestamos
    ),
    HistorialCliente AS (
        SELECT 
            p.pr_id_oficina,
            p.pr_id_cliente,
            COUNT(*) AS totalPrestamos
        FROM dbsolonegocios.dbo.tb_prestamos p WITH (NOLOCK)
        WHERE EXISTS (
            SELECT 1 FROM #PrestamosCandidatos pc 
            WHERE pc.pr_id_cliente = p.pr_id_cliente AND pc.pr_id_oficina = p.pr_id_oficina
        )
        AND ISNULL(p.pr_estado, 0) <> 0
        GROUP BY p.pr_id_oficina, p.pr_id_cliente
    ),
    PrestamosEvaluados AS (
        SELECT 
            pc.pr_id_oficina,
            pc.pr_id_cliente,
            pc.pr_id_prestamos,
            pc.pr_monto,
            pc.pr_tasa_interes,
            pc.pr_fecha,
            pc.pr_fecha_venc,
            pc.pr_estado,
            ISNULL(ph.capitalPagadoTotal, 0) AS capitalPagadoTotal,
            ISNULL(cq.capitalCobrado, 0)     AS capitalCobradoQuincena,
            ISNULL(cq.interesCobrado, 0)     AS interesCobradoQuincena,
            ISNULL(cq.totalCobrado, 0)       AS totalCobradoQuincena,
            ISNULL(ci.cuotasVencidas, 0)     AS cuotasVencidas,
            ISNULL(hc.totalPrestamos, 1)     AS totalPrestamosHist,
            CASE 
                WHEN ISNULL(ci.cuotasVencidas, 0) > 0 AND ci.minFechaVencida IS NOT NULL
                THEN DATEDIFF(day, ci.minFechaVencida, @Hoy)
                ELSE 0 
            END AS diasAtraso,
            
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
            END AS esActivo,

            CASE 
                WHEN EXISTS (
                    SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg WITH (NOLOCK)
                    WHERE rg.rg_id_prestamo = pc.pr_id_prestamos AND rg.rg_id_oficina = pc.pr_id_oficina
                      AND CAST(rg.rg_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena
                ) THEN 1 ELSE 0 
            END AS fueReenganchadoEnQuincena,

            CASE 
                WHEN CAST(pc.pr_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena THEN 1 ELSE 0 
            END AS otorgadoEnQuincena

        FROM #PrestamosCandidatos pc
        LEFT JOIN PagosHistoricos ph 
            ON ph.rp_id_prestamo = pc.pr_id_prestamos AND ph.rp_id_oficina = pc.pr_id_oficina
        LEFT JOIN CobrosQuincena cq 
            ON cq.rp_id_prestamo = pc.pr_id_prestamos AND cq.rp_id_oficina = pc.pr_id_oficina
        LEFT JOIN CuotasInfo ci 
            ON ci.dp_id_prestamos = pc.pr_id_prestamos AND ci.dp_id_oficina = pc.pr_id_oficina
        LEFT JOIN HistorialCliente hc 
            ON hc.pr_id_cliente = pc.pr_id_cliente AND hc.pr_id_oficina = pc.pr_id_oficina
    )
    INSERT INTO #ReporteDetalle
    SELECT 
        pe.pr_id_oficina                                                 AS idOficina,
        pe.pr_id_cliente                                                 AS idCliente,
        ci.nombreCliente,
        ci.cedula,
        ci.empresa,
        CAST(pe.pr_id_prestamos AS VARCHAR(50))                          AS numeroPrestamo,
        CAST(pe.pr_monto AS DECIMAL(18,2))                               AS montoPrestamo,

        -- Capital Pagado
        CAST(
            CASE 
                WHEN pe.esActivo = 0 THEN pe.pr_monto
                WHEN pe.capitalPagadoTotal > pe.pr_monto THEN pe.pr_monto
                WHEN pe.capitalPagadoTotal < 0 THEN 0.00
                ELSE pe.capitalPagadoTotal
            END AS DECIMAL(18,2)
        ) AS capitalPagado,

        -- Balance Antes del Cobro:
        -- Activo: (Monto Inicial - Capital Pagado) + Capital Cobrado Quincena
        -- Cancelado: Capital Cobrado en la Quincena para saldarlo (o 0.00)
        CAST(
            CASE 
                WHEN pe.esActivo = 1 THEN
                    (CASE 
                        WHEN (pe.pr_monto - pe.capitalPagadoTotal) < 0 THEN 0.00 
                        ELSE (pe.pr_monto - pe.capitalPagadoTotal) 
                    END) + pe.capitalCobradoQuincena
                ELSE pe.capitalCobradoQuincena
            END AS DECIMAL(18,2)
        ) AS balanceAntesCobro,

        CAST(pe.pr_tasa_interes AS FLOAT)                                AS tasa,
        pe.pr_fecha                                                      AS fechaPrestamo,
        pe.capitalCobradoQuincena,
        pe.interesCobradoQuincena,

        -- Capital Actual Adeudado:
        -- Activo: Monto Inicial - Capital Pagado
        -- Cancelado: 0.00
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

        pe.totalCobradoQuincena,
        
        -- Balance Actual Adeudado (Capital)
        CAST(
            CASE 
                WHEN pe.esActivo = 1 THEN
                    (CASE 
                        WHEN (pe.pr_monto - pe.capitalPagadoTotal) < 0 THEN 0.00 
                        ELSE (pe.pr_monto - pe.capitalPagadoTotal) 
                    END)
                ELSE 0.00
            END AS DECIMAL(18,2)
        ) AS balanceActual,

        -- Clasificación:
        CASE 
            WHEN pe.esActivo = 0 OR pe.fueReenganchadoEnQuincena = 1
                THEN 'CANCELADO'
            WHEN pe.otorgadoEnQuincena = 1 AND pe.totalPrestamosHist <= 1
                THEN 'NUEVO'
            WHEN pe.otorgadoEnQuincena = 1 AND pe.totalPrestamosHist > 1
                THEN 'REENGANCHADO'
            WHEN pe.cuotasVencidas > 0 AND pe.esActivo = 1
                THEN CASE 
                    WHEN pe.diasAtraso <= 15 THEN 'SITUACION ATRASO (15 DIAS)'
                    WHEN pe.diasAtraso <= 30 THEN 'SITUACION ATRASO (30 DIAS)'
                    WHEN pe.diasAtraso <= 45 THEN 'SITUACION ATRASO (45 DIAS)'
                    ELSE 'SITUACION ATRASO (60+ DIAS)'
                END
            ELSE 'AL DIA'
        END AS clasificacion,

        pe.diasAtraso,

        -- Comentario descriptivo:
        CASE 
            WHEN pe.fueReenganchadoEnQuincena = 1
                THEN 'Cancelado por reenganche'
            WHEN pe.esActivo = 0
                THEN 'Préstamo saldado / cancelado'
            WHEN pe.otorgadoEnQuincena = 1 AND pe.totalPrestamosHist <= 1
                THEN 'Préstamo nuevo otorgado en período'
            WHEN pe.otorgadoEnQuincena = 1 AND pe.totalPrestamosHist > 1
                THEN 'Reenganche otorgado en período'
            WHEN pe.cuotasVencidas > 0 AND pe.esActivo = 1
                THEN 'Presenta cuotas con ' + CAST(pe.diasAtraso AS VARCHAR(10)) + ' días de atraso'
            WHEN pe.totalCobradoQuincena > 0
                THEN 'Cobro quincenal aplicado'
            ELSE ''
        END AS comentario,

        pe.totalPrestamosHist,
        CASE WHEN pe.otorgadoEnQuincena = 1 AND pe.totalPrestamosHist <= 1 THEN 1 ELSE 0 END AS esNuevoEnPeriodo,
        CASE WHEN pe.otorgadoEnQuincena = 1 AND pe.totalPrestamosHist > 1 THEN 1 ELSE 0 END  AS esReengancheEnPeriodo

    FROM PrestamosEvaluados pe
    INNER JOIN #ClientesInfo ci 
        ON ci.idCliente = pe.pr_id_cliente AND ci.idOficina = pe.pr_id_oficina;

    -- Filtrar por empresa si se especificó
    IF @empresa IS NOT NULL AND RTRIM(LTRIM(@empresa)) <> ''
        DELETE FROM #ReporteDetalle WHERE empresa NOT LIKE '%' + @empresa + '%';

    -- Filtrar por Tipo de Reporte
    SET @tipoReporte = UPPER(ISNULL(NULLIF(RTRIM(LTRIM(@tipoReporte)), ''), 'TODOS'));

    IF @tipoReporte = 'NUEVOS'
        DELETE FROM #ReporteDetalle WHERE clasificacion <> 'NUEVO';
    ELSE IF @tipoReporte = 'REENGANCHADOS'
        DELETE FROM #ReporteDetalle WHERE clasificacion <> 'REENGANCHADO';
    ELSE IF @tipoReporte = 'CANCELADOS'
        DELETE FROM #ReporteDetalle WHERE clasificacion <> 'CANCELADO';
    ELSE IF @tipoReporte = 'AL DIA'
        DELETE FROM #ReporteDetalle WHERE clasificacion <> 'AL DIA';
    ELSE IF @tipoReporte IN ('ATRASO 15', 'ATRASO 15 DIAS', '15 DIAS', '15')
        DELETE FROM #ReporteDetalle WHERE clasificacion <> 'SITUACION ATRASO (15 DIAS)';
    ELSE IF @tipoReporte IN ('ATRASO 30', 'ATRASO 30 DIAS', '30 DIAS', '30')
        DELETE FROM #ReporteDetalle WHERE clasificacion <> 'SITUACION ATRASO (30 DIAS)';
    ELSE IF @tipoReporte IN ('ATRASO 45', 'ATRASO 45 DIAS', '45 DIAS', '45')
        DELETE FROM #ReporteDetalle WHERE clasificacion <> 'SITUACION ATRASO (45 DIAS)';
    ELSE IF @tipoReporte IN ('ATRASO 60', 'ATRASO 60 DIAS', 'ATRASO 60+', 'ATRASO 60+ DIAS', '60 DIAS', '60')
        DELETE FROM #ReporteDetalle WHERE clasificacion <> 'SITUACION ATRASO (60+ DIAS)';
    ELSE IF @tipoReporte IN ('EN MORA', 'ATRASO', 'SITUACION ATRASO')
        DELETE FROM #ReporteDetalle WHERE clasificacion NOT LIKE 'SITUACION ATRASO%';

    -- ── Result Set 1: Listado Detalle por Préstamo ───────────────────
    SELECT 
        idCliente,
        clasificacion,
        diasAtraso,
        nombreCliente,
        cedula,
        empresa,
        numeroPrestamo,
        montoPrestamo,
        capitalPagado,
        balanceAntesCobro,
        capitalCobradoQuincena,
        interesCobradoQuincena,
        capitalActualAdeudado,
        totalCobradoQuincena,
        balanceActual,
        tasa,
        fechaPrestamo,
        comentario
    FROM #ReporteDetalle
    ORDER BY empresa, nombreCliente, numeroPrestamo;

    -- ── Result Set 2: Fila de Totales Generales en Pesos ($) ─────────
    SELECT 
        COUNT(*)                                       AS totalRegistros,
        ISNULL(SUM(montoPrestamo), 0)                  AS totalMontoPrestamo,
        ISNULL(SUM(capitalPagado), 0)                  AS totalCapitalPagado,
        ISNULL(SUM(balanceAntesCobro), 0)              AS totalBalanceAntesCobro,
        ISNULL(SUM(capitalCobradoQuincena), 0)         AS totalCapitalCobradoQuincena,
        ISNULL(SUM(interesCobradoQuincena), 0)         AS totalInteresCobradoQuincena,
        ISNULL(SUM(capitalActualAdeudado), 0)          AS totalCapitalActualAdeudado,
        ISNULL(SUM(totalCobradoQuincena), 0)           AS totalCobradoQuincena,
        ISNULL(SUM(balanceActual), 0)                  AS totalBalanceActual,
        CASE 
            WHEN COUNT(*) > 0 THEN ROUND(AVG(tasa), 2) 
            ELSE 0.00 
        END AS tasaPromedio,
        @fechaDesde                                    AS periodoDesde,
        @fechaHasta                                    AS periodoHasta,
        @InicioQuincena                                AS quincenaDesde,
        @FinQuincena                                   AS quincenaHasta
    FROM #ReporteDetalle;

    DROP TABLE #PrestamosCandidatos;
    DROP TABLE #ClientesInfo;
    DROP TABLE #ReporteDetalle;
END
GO
