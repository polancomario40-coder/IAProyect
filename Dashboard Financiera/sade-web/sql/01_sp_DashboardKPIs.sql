-- =========================================================================================
-- SP: cxcDashboardKPIs (v4 - Cartera Activa Real sin Duplicados Históricos y sin N.CREDITO)
-- =========================================================================================
-- Correcciones aplicadas:
--   1. Cartera Activa (Capital Colocado Activo y Original):
--      Evalúa el préstamo activo actual por cliente (rn = 1 por oficina+cliente con pr_estado = 1)
--      donde el capital actual adeudado (pr_monto - capitalPagado real) > 0.
--      En dbsolonegocios, pr_balance nunca se rebaja al aplicar pagos y existen préstamos
--      históricos reenganchados que quedaron con pr_estado = 1; deduplicar por cliente activo
--      evita que el Capital Colocado se dispare a cientos de millones.
--   2. Cobros del Mes:
--      Excluye Notas de Crédito / Reenganches (rp_forma_pago = 'N.CREDITO', tb_notas_credito,
--      y cierres administrativos 'SALDO DE PRESTAMO' sin interés o de reenganche).
--   3. Intereses y Moras Pendientes:
--      Filtra únicamente cuotas pendientes reales (dp_estado = 1) uniendo por (id_oficina, id_prestamos)
--      sobre préstamos activos vigentes, saneando valores corruptos por interés compuesto.
-- =========================================================================================
USE Financiera
GO

IF OBJECT_ID('dbo.cxcDashboardKPIs', 'P') IS NOT NULL
    DROP PROCEDURE dbo.cxcDashboardKPIs
GO

CREATE PROCEDURE dbo.cxcDashboardKPIs
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Hoy       DATE = CAST(GETDATE() AS DATE);
    DECLARE @InicioMes DATE = DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1);
    DECLARE @FinMes    DATE = EOMONTH(GETDATE());

    -- -------------------------------------------------------------------------------------
    -- 1. UNIVERSO DE PRÉSTAMOS ACTIVOS REALES (1 préstamo vigente real por cliente)
    -- -------------------------------------------------------------------------------------
    CREATE TABLE #PrestamosActivosReales (
        idOficina               INT,
        idPrestamo              INT,
        idCliente               INT,
        montoOriginal           DECIMAL(18,2),
        tasaInteres             DECIMAL(18,2),
        capitalPagado           DECIMAL(18,2),
        capitalActualAdeudado   DECIMAL(18,2),
        interesPendiente        DECIMAL(18,2),
        moraPendiente           DECIMAL(18,2),
        tieneCuotaVencida       INT
    );

    ;WITH PagosRealesPorPrestamo AS (
        SELECT
            rp.rp_id_oficina,
            rp.rp_id_prestamo,
            ISNULL(SUM(rp.rp_capital), 0) AS capitalPagado
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp
        WHERE rp.rp_estado = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
          AND ISNULL(rp.rp_observacion, '') NOT LIKE '%Nota de Credito%'
          AND ISNULL(rp.rp_observacion, '') NOT LIKE '%Reenganche%'
          AND NOT EXISTS (
              SELECT 1 FROM dbsolonegocios.dbo.tb_notas_credito nc
              WHERE nc.nc_recibo_pago = rp.rp_id_recibo AND nc.nc_id_oficina = rp.rp_id_oficina
          )
          AND NOT (
              ISNULL(rp.rp_observacion, '') = 'SALDO DE PRESTAMO'
              AND (
                  ISNULL(rp.rp_interes, 0) = 0
                  OR EXISTS (
                      SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg
                      WHERE rg.rg_id_prestamo = rp.rp_id_prestamo AND rg.rg_id_oficina = rp.rp_id_oficina
                  )
              )
          )
        GROUP BY rp.rp_id_oficina, rp.rp_id_prestamo
    ),
    CuotasPendientes AS (
        SELECT
            dp.dp_id_oficina,
            dp.dp_id_prestamos,
            ISNULL(SUM(dp.dp_saldo_capital), 0) AS saldoCapitalCuotas,
            ISNULL(SUM(dp.dp_saldo_interes), 0) AS saldoInteresCuotas,
            ISNULL(SUM(ISNULL(NULLIF(dp.dp_saldo_mora, 0), dp.dp_mora)), 0) AS saldoMoraCuotas,
            MAX(CASE WHEN CAST(dp.dp_fecha_venc AS DATE) < @Hoy AND (ISNULL(dp.dp_saldo_capital, 0) + ISNULL(dp.dp_saldo_interes, 0)) > 0 THEN 1 ELSE 0 END) AS tieneAtraso
        FROM dbsolonegocios.dbo.tb_detalle_prestamos dp
        WHERE dp.dp_estado = 1
        GROUP BY dp.dp_id_oficina, dp.dp_id_prestamos
    ),
    PrestamosVigentes AS (
        SELECT
            p.pr_id_oficina,
            p.pr_id_prestamos,
            p.pr_id_cliente,
            CAST(ISNULL(p.pr_monto, 0) AS DECIMAL(18,2)) AS montoOriginal,
            CAST(ISNULL(p.pr_tasa_interes, 0) AS DECIMAL(18,2)) AS tasaInteres,
            CAST(ISNULL(pag.capitalPagado, 0) AS DECIMAL(18,2)) AS capitalPagado,
            CAST(
                CASE 
                    WHEN (ISNULL(p.pr_monto, 0) - ISNULL(pag.capitalPagado, 0)) < 0 THEN 0.00
                    ELSE (ISNULL(p.pr_monto, 0) - ISNULL(pag.capitalPagado, 0))
                END AS DECIMAL(18,2)
            ) AS capitalActualAdeudado,
            ISNULL(cp.saldoCapitalCuotas, 0) AS saldoCapitalCuotas,
            ISNULL(cp.saldoInteresCuotas, 0) AS saldoInteresCuotas,
            ISNULL(cp.saldoMoraCuotas, 0) AS saldoMoraCuotas,
            ISNULL(cp.tieneAtraso, 0) AS tieneAtraso,
            ROW_NUMBER() OVER (
                PARTITION BY p.pr_id_oficina, p.pr_id_cliente
                ORDER BY p.pr_fecha DESC, p.pr_id_prestamos DESC
            ) AS rn
        FROM dbsolonegocios.dbo.tb_prestamos p
        LEFT JOIN PagosRealesPorPrestamo pag
            ON pag.rp_id_prestamo = p.pr_id_prestamos AND pag.rp_id_oficina = p.pr_id_oficina
        LEFT JOIN CuotasPendientes cp
            ON cp.dp_id_prestamos = p.pr_id_prestamos AND cp.dp_id_oficina = p.pr_id_oficina
        WHERE p.pr_estado = 1
          AND NOT EXISTS (
              SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg
              WHERE rg.rg_id_prestamo = p.pr_id_prestamos AND rg.rg_id_oficina = p.pr_id_oficina
          )
    )
    INSERT INTO #PrestamosActivosReales
    SELECT
        pv.pr_id_oficina,
        pv.pr_id_prestamos,
        pv.pr_id_cliente,
        pv.montoOriginal,
        pv.tasaInteres,
        pv.capitalPagado,
        pv.capitalActualAdeudado,
        -- Saneamiento de interés pendiente ante posible bucle de usp_proceso_interes compuesto
        CAST(
            CASE
                WHEN pv.saldoInteresCuotas < 0 THEN 0.00
                WHEN pv.saldoInteresCuotas > pv.montoOriginal THEN ROUND(pv.capitalActualAdeudado * (pv.tasaInteres / 100.0), 2)
                ELSE pv.saldoInteresCuotas
            END AS DECIMAL(18,2)
        ) AS interesPendiente,
        -- Saneamiento de mora pendiente ante posible acumulación exponencial de usp_proceso_mora
        CAST(
            CASE
                WHEN pv.saldoMoraCuotas < 0 THEN 0.00
                WHEN pv.saldoMoraCuotas > pv.capitalActualAdeudado THEN ROUND(pv.capitalActualAdeudado * (pv.tasaInteres / 100.0), 2)
                ELSE pv.saldoMoraCuotas
            END AS DECIMAL(18,2)
        ) AS moraPendiente,
        pv.tieneAtraso
    FROM PrestamosVigentes pv
    WHERE pv.rn = 1
      AND pv.capitalActualAdeudado > 0;

    DECLARE @TotalPrestamosActivos INT           = 0;
    DECLARE @CapitalActivoOriginal DECIMAL(18,2) = 0.00;
    DECLARE @CapitalPendiente      DECIMAL(18,2) = 0.00;
    DECLARE @InteresPendiente      DECIMAL(18,2) = 0.00;
    DECLARE @MorasPendientes       DECIMAL(18,2) = 0.00;
    DECLARE @PrestamosAtrasados    INT           = 0;

    SELECT
        @TotalPrestamosActivos = COUNT(*),
        @CapitalActivoOriginal = ISNULL(SUM(montoOriginal), 0),
        @CapitalPendiente      = ISNULL(SUM(capitalActualAdeudado), 0),
        @InteresPendiente      = ISNULL(SUM(interesPendiente), 0),
        @MorasPendientes       = ISNULL(SUM(moraPendiente), 0),
        @PrestamosAtrasados    = ISNULL(SUM(tieneCuotaVencida), 0)
    FROM #PrestamosActivosReales;

    DROP TABLE #PrestamosActivosReales;

    -- Tasa de mora
    DECLARE @TasaMora DECIMAL(10,2) = 0.00;
    IF @TotalPrestamosActivos > 0
    BEGIN
        SET @TasaMora = CAST(@PrestamosAtrasados AS DECIMAL(10,2)) / CAST(@TotalPrestamosActivos AS DECIMAL(10,2)) * 100.0;
    END

    -- -------------------------------------------------------------------------------------
    -- 2. COBROS REALES DEL MES ACTUAL (Excluyendo N.CREDITO, Reenganches y Cierres Admin)
    -- -------------------------------------------------------------------------------------
    DECLARE @CapitalCobradoMes DECIMAL(18,2) = 0.00;
    DECLARE @InteresCobradoMes DECIMAL(18,2) = 0.00;
    DECLARE @MoraCobradaMes    DECIMAL(18,2) = 0.00;
    DECLARE @TotalCobradoMes   DECIMAL(18,2) = 0.00;
    DECLARE @RecibosMes        INT           = 0;

    SELECT
        @CapitalCobradoMes = ISNULL(SUM(rp.rp_capital), 0),
        @InteresCobradoMes = ISNULL(SUM(rp.rp_interes), 0),
        @MoraCobradaMes    = ISNULL(SUM(rp.rp_mora), 0),
        @TotalCobradoMes   = ISNULL(SUM(rp.rp_capital + rp.rp_interes + ISNULL(rp.rp_mora, 0)), 0),
        @RecibosMes        = COUNT(*)
    FROM dbsolonegocios.dbo.tb_recibo_pagos rp
    WHERE rp.rp_estado = 1
      AND CAST(rp.rp_fecha AS DATE) BETWEEN @InicioMes AND @FinMes
      AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
      AND ISNULL(rp.rp_observacion, '') NOT LIKE '%Nota de Credito%'
      AND ISNULL(rp.rp_observacion, '') NOT LIKE '%Reenganche%'
      AND NOT EXISTS (
          SELECT 1 FROM dbsolonegocios.dbo.tb_notas_credito nc
          WHERE nc.nc_recibo_pago = rp.rp_id_recibo AND nc.nc_id_oficina = rp.rp_id_oficina
      )
      AND NOT (
          ISNULL(rp.rp_observacion, '') = 'SALDO DE PRESTAMO'
          AND (
              ISNULL(rp.rp_interes, 0) = 0
              OR EXISTS (
                  SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg
                  WHERE rg.rg_id_prestamo = rp.rp_id_prestamo AND rg.rg_id_oficina = rp.rp_id_oficina
              )
          )
      );

    -- -------------------------------------------------------------------------------------
    -- RESULT SET FINAL
    -- -------------------------------------------------------------------------------------
    SELECT
        -- Cartera Activa
        @CapitalPendiente       AS capitalPendiente,
        @CapitalActivoOriginal  AS capitalOriginal,
        @TotalPrestamosActivos  AS totalPrestamos,

        -- Cobros del Mes
        @CapitalCobradoMes      AS capitalCobradoMes,
        @InteresCobradoMes      AS interesCobradoMes,
        @MoraCobradaMes         AS moraCobradaMes,
        @TotalCobradoMes        AS totalCobradoMes,
        @RecibosMes             AS recibosMes,

        -- Cartera Vencida
        @PrestamosAtrasados     AS prestamosAtrasados,
        @TasaMora               AS tasaMora,

        -- Intereses y Moras Pendientes reales de cartera activa
        @InteresPendiente       AS interesesPendientes,
        @MorasPendientes        AS morasPendientes,

        -- Metadata
        @InicioMes              AS periodoInicio,
        @FinMes                 AS periodoFin,
        GETDATE()               AS generadoEn;
END
GO
