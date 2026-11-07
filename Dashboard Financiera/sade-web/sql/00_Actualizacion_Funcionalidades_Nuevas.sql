-- =========================================================================================
-- SCRIPT MAESTRO CONSOLIDADO: ACTUALIZACIÓN TOTAL DE PROCEDIMIENTOS E INTERFACES SADE WEB
-- Incluye todos los Stored Procedures del Dashboard, Reportes Quincenales e Interfaces Windows
-- =========================================================================================
USE Financiera
GO

-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- SCRIPT: 01_sp_DashboardKPIs.sql
-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
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

GO

-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- SCRIPT: 02_sp_CobrosporMes.sql
-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- =========================================================================================
-- SP: cxcCobrosporMes (v4 - Cobros Reales por Mes sin Notas de Crédito ni Reenganches)
-- =========================================================================================
-- Correcciones aplicadas:
--   1. Lee directamente de dbsolonegocios.dbo.tb_recibo_pagos con rp_estado = 1.
--   2. Excluye Notas de Crédito y liquidaciones internas por Reenganche (rp_forma_pago = 'N.CREDITO',
--      tb_notas_credito, tb_reenganche y cierres administrativos 'SALDO DE PRESTAMO' sin interés),
--      que anteriormente disparaban el Capital Cobrado en meses como noviembre o el mes actual.
--   3. Desglosa con total precisión: capital, interés, mora y total cobrado real.
--   4. Mantiene zero-fill para meses sin cobros.
-- =========================================================================================
USE Financiera
GO

IF OBJECT_ID('dbo.cxcCobrosporMes', 'P') IS NOT NULL
    DROP PROCEDURE dbo.cxcCobrosporMes
GO

CREATE PROCEDURE dbo.cxcCobrosporMes
    @meses INT = 12
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @FechaInicio DATE = DATEADD(MONTH, -(@meses - 1),
                                 DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1));

    -- Serie de meses para zero-fill
    ;WITH Meses AS (
        SELECT TOP (@meses)
            DATEFROMPARTS(
                YEAR(DATEADD(MONTH, ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1, @FechaInicio)),
                MONTH(DATEADD(MONTH, ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1, @FechaInicio)),
                1
            ) AS mesFecha
        FROM sys.all_objects
    ),
    CobrosPorMes AS (
        SELECT
            DATEFROMPARTS(YEAR(rp.rp_fecha), MONTH(rp.rp_fecha), 1) AS mesFecha,
            ISNULL(SUM(rp.rp_capital), 0)      AS capitalCobrado,
            ISNULL(SUM(rp.rp_interes), 0)      AS interesCobrado,
            ISNULL(SUM(rp.rp_mora), 0)         AS moraCobrada,
            ISNULL(SUM(rp.rp_capital + rp.rp_interes + ISNULL(rp.rp_mora, 0)), 0) AS totalCobrado,
            COUNT(*)                           AS cantidadRecibos
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp
        WHERE rp.rp_estado = 1
          AND CAST(rp.rp_fecha AS DATE) >= @FechaInicio
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
        GROUP BY DATEFROMPARTS(YEAR(rp.rp_fecha), MONTH(rp.rp_fecha), 1)
    )
    SELECT
        m.mesFecha,
        FORMAT(m.mesFecha, 'MMM yyyy', 'es-DO')        AS mesEtiqueta,
        ISNULL(cpm.capitalCobrado, 0)                  AS capitalCobrado,
        ISNULL(cpm.interesCobrado, 0)                  AS interesCobrado,
        ISNULL(cpm.moraCobrada, 0)                     AS moraCobrada,
        ISNULL(cpm.totalCobrado, 0)                    AS totalCobrado,
        ISNULL(cpm.cantidadRecibos, 0)                 AS cantidadRecibos
    FROM Meses m
    LEFT JOIN CobrosPorMes cpm ON cpm.mesFecha = m.mesFecha
    ORDER BY m.mesFecha;
END
GO

GO

-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- SCRIPT: 03_sp_EstadoPrestamo.sql
-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- =========================================================================================
-- SP: cxcEstadoPrestamo (v4 - Con Creador y Monto para Saldar Hoy con Regla de Gracia)
-- =========================================================================================
USE Financiera
GO

IF OBJECT_ID('dbo.cxcEstadoPrestamo', 'P') IS NOT NULL
    DROP PROCEDURE dbo.cxcEstadoPrestamo
GO

CREATE PROCEDURE dbo.cxcEstadoPrestamo
    @numeroCxc VARCHAR(50)   -- numero del prestamo, ej. '17481'
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Hoy DATE = CAST(GETDATE() AS DATE);
    DECLARE @idPrestamoInt INT = TRY_CAST(@numeroCxc AS INT);

    -- Verificar si existe en dbsolonegocios
    IF NOT EXISTS (SELECT 1 FROM dbsolonegocios.dbo.tb_prestamos WHERE pr_id_prestamos = @idPrestamoInt)
       AND NOT EXISTS (SELECT 1 FROM Financiera.dbo.Cxc WHERE (Cxc = @numeroCxc OR idDocumento = @numeroCxc) AND idTipoDocumento = 'FT')
    BEGIN
        -- Retornar 4 result sets vacios para mantener contrato con el backend
        SELECT CAST(NULL AS VARCHAR(50)) AS numeroPrestamo WHERE 1=0;
        SELECT CAST(NULL AS INT) AS numCuota WHERE 1=0;
        SELECT CAST(NULL AS VARCHAR(50)) AS numeroPago WHERE 1=0;
        SELECT CAST(0 AS INT) AS totalCuotas, CAST(0 AS INT) AS totalRecibos;
        RETURN;
    END

    -- -------------------------------------------------------------------------------------
    -- DATOS BASE DEL PRESTAMO (dbsolonegocios con fallback a Financiera)
    -- -------------------------------------------------------------------------------------
    DECLARE @NombreCliente    VARCHAR(200) = '';
    DECLARE @IdCliente        INT          = 0;
    DECLARE @FechaPrestamo    DATETIME     = NULL;
    DECLARE @TasaInteres      FLOAT        = 0.0;
    DECLARE @Vencimiento      DATETIME     = NULL;
    DECLARE @UsuarioCreador   VARCHAR(100) = 'SADE';
    DECLARE @Referencia       VARCHAR(100) = '';

    -- Valores Iniciales
    DECLARE @CapitalInicial   DECIMAL(18,2) = 0.00;
    DECLARE @InteresInicial   DECIMAL(18,2) = 0.00;
    DECLARE @TotalInicial     DECIMAL(18,2) = 0.00;

    -- Valores Pagados
    DECLARE @CapitalPagado    DECIMAL(18,2) = 0.00;
    DECLARE @InteresPagado    DECIMAL(18,2) = 0.00;
    DECLARE @MoraPagada       DECIMAL(18,2) = 0.00;
    DECLARE @TotalPagado      DECIMAL(18,2) = 0.00;

    -- Valores Balance
    DECLARE @CapitalBalance   DECIMAL(18,2) = 0.00;
    DECLARE @InteresBalance   DECIMAL(18,2) = 0.00;
    DECLARE @MoraBalance      DECIMAL(18,2) = 0.00;
    DECLARE @TotalBalance     DECIMAL(18,2) = 0.00;

    -- Valores Vencidos
    DECLARE @CapitalVencido   DECIMAL(18,2) = 0.00;
    DECLARE @InteresVencido   DECIMAL(18,2) = 0.00;
    DECLARE @MoraVencida      DECIMAL(18,2) = 0.00;
    DECLARE @TotalVencido     DECIMAL(18,2) = 0.00;

    -- Proyección para Cancelación / Saldar
    DECLARE @UltimoVencimientoPasado DATETIME = NULL;
    DECLARE @DiasDesdeVencimiento    INT      = 0;
    DECLARE @MontoSaldarHoy          DECIMAL(18,2) = 0.00;

    -- Estado general
    DECLARE @EstadoPrestamo   VARCHAR(30)  = 'AL DIA';

    -- 1. Leer encabezado desde tb_prestamos
    SELECT
        @IdCliente      = p.pr_id_cliente,
        @NombreCliente  = ISNULL(c.cl_nombre + ' ' + ISNULL(c.cl_apellido, ''), 'CLIENTE #' + CAST(p.pr_id_cliente AS VARCHAR(20))),
        @FechaPrestamo  = p.pr_fecha,
        @TasaInteres    = ISNULL(CAST(p.pr_tasa_interes AS FLOAT), 0.0),
        @Vencimiento    = p.pr_fecha_venc,
        @UsuarioCreador = CASE 
                            WHEN p.pr_operador IS NOT NULL AND p.pr_operador <> '' AND p.pr_operador <> '0' 
                                THEN p.pr_operador
                            WHEN c.cl_operador IS NOT NULL AND c.cl_operador <> '' AND c.cl_operador <> '0' 
                                THEN c.cl_operador
                            ELSE 'SADE'
                          END,
        @Referencia     = ISNULL(p.pr_referencia, ''),
        @CapitalInicial = ISNULL(p.pr_monto, 0.00),
        @InteresInicial = ISNULL(p.pr_interes, 0.00),
        @TotalInicial   = ISNULL(p.pr_monto, 0.00) + ISNULL(p.pr_interes, 0.00)
    FROM dbsolonegocios.dbo.tb_prestamos p
    LEFT JOIN dbsolonegocios.dbo.tb_clientes c ON c.cl_id_cliente = p.pr_id_cliente
    WHERE p.pr_id_prestamos = @idPrestamoInt;

    -- Fallback si no encontro en dbsolonegocios pero esta en Financiera
    IF @CapitalInicial = 0
    BEGIN
        SELECT
            @IdCliente      = idCliente,
            @NombreCliente  = ISNULL(Cliente, ''),
            @FechaPrestamo  = Fecha,
            @TasaInteres    = ISNULL(Tasa, 0.0),
            @Vencimiento    = Vencimiento,
            @UsuarioCreador = ISNULL(Usuario, 'SADE'),
            @Referencia     = ISNULL(Concepto, ''),
            @CapitalInicial = ISNULL(Valor, 0.00),
            @InteresInicial = 0.00,
            @TotalInicial   = ISNULL(Valor, 0.00)
        FROM Financiera.dbo.Cxc
        WHERE (Cxc = @numeroCxc OR idDocumento = @numeroCxc) AND idTipoDocumento = 'FT';
    END

    -- 2. Calcular Pagado acumulado desde tb_recibo_pagos (excluyendo Notas de Crédito internas)
    SELECT
        @CapitalPagado = ISNULL(SUM(rp_capital), 0.00),
        @InteresPagado = ISNULL(SUM(rp_interes), 0.00),
        @MoraPagada    = ISNULL(SUM(rp_mora), 0.00),
        @TotalPagado   = ISNULL(SUM(rp_total_pagado), 0.00)
    FROM dbsolonegocios.dbo.tb_recibo_pagos
    WHERE rp_id_prestamo = @idPrestamoInt
      AND rp_estado = 1
      AND UPPER(LTRIM(RTRIM(ISNULL(rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC');

    -- Si no habia recibos en solonegocios pero hay en Financiera (CxcDet)
    IF @CapitalPagado = 0
    BEGIN
        SELECT
            @CapitalPagado = ISNULL(SUM(CASE WHEN d.Referencia LIKE 'RP:%' OR d.Referencia NOT LIKE '%INTERES%' THEN d.Valor ELSE 0 END), 0),
            @InteresPagado = ISNULL(SUM(CASE WHEN d.Referencia LIKE '%INTERES%' THEN d.Valor ELSE 0 END), 0),
            @TotalPagado   = ISNULL(SUM(d.Valor), 0)
        FROM Financiera.dbo.CxcDet d
        INNER JOIN Financiera.dbo.Cxc ft ON ft.idCxc = d.idCxcDebito
        WHERE (ft.Cxc = @numeroCxc OR ft.idDocumento = @numeroCxc) AND ft.idTipoDocumento = 'FT';
    END

    -- 3. Calcular Balances restantes
    -- Desde cuotas detalladas pendientes (dp_estado = 1)
    SELECT
        @CapitalBalance = ISNULL(SUM(dp_saldo_capital), 0.00),
        @InteresBalance = ISNULL(SUM(dp_saldo_interes), 0.00)
    FROM dbsolonegocios.dbo.tb_detalle_prestamos
    WHERE dp_id_prestamos = @idPrestamoInt
      AND dp_estado = 1;

    -- Si no habia saldo detallado, calcular por diferencia
    IF @CapitalBalance = 0 AND (@CapitalInicial - @CapitalPagado) > 0
    BEGIN
        SET @CapitalBalance = @CapitalInicial - @CapitalPagado;
        SET @InteresBalance = CASE WHEN (@InteresInicial - @InteresPagado) > 0 THEN @InteresInicial - @InteresPagado ELSE 0.00 END;
    END

    SET @MoraBalance  = 0.00;
    SET @TotalBalance = @CapitalBalance + @InteresBalance;

    -- 4. Calcular Valores Vencidos (cuotas vencidas no saldadas)
    DECLARE @CuotasVencidas INT = 0;

    SELECT
        @CapitalVencido = ISNULL(SUM(dp_saldo_capital), 0.00),
        @InteresVencido = ISNULL(SUM(dp_saldo_interes), 0.00),
        @MoraVencida    = ISNULL(SUM(dp_mora), 0.00),
        @CuotasVencidas = COUNT(*)
    FROM dbsolonegocios.dbo.tb_detalle_prestamos
    WHERE dp_id_prestamos = @idPrestamoInt
      AND dp_estado = 1
      AND CAST(dp_fecha_venc AS DATE) < @Hoy;

    SET @TotalVencido = @CapitalVencido + @InteresVencido + @MoraVencida;

    -- 5. Determinar estado
    IF @TotalBalance <= 0
        SET @EstadoPrestamo = 'SALDADO';
    ELSE IF @TotalVencido > 0 OR (CAST(@Vencimiento AS DATE) < @Hoy AND @TotalBalance > 0)
        SET @EstadoPrestamo = 'ATRASADO';
    ELSE
        SET @EstadoPrestamo = 'AL DIA';

    -- 6. Cálculo de "Monto para Saldar Hoy" (Regla de gracia de 5 días)
    SELECT @UltimoVencimientoPasado = MAX(dp_fecha_venc)
    FROM dbsolonegocios.dbo.tb_detalle_prestamos
    WHERE dp_id_prestamos = @idPrestamoInt
      AND dp_estado <> 0
      AND CAST(dp_fecha_venc AS DATE) <= @Hoy;

    IF @UltimoVencimientoPasado IS NULL
        SET @UltimoVencimientoPasado = @FechaPrestamo;

    IF @UltimoVencimientoPasado IS NOT NULL
        SET @DiasDesdeVencimiento = DATEDIFF(day, CAST(@UltimoVencimientoPasado AS DATE), @Hoy);
    ELSE
        SET @DiasDesdeVencimiento = 999;

    IF @TotalBalance <= 0
    BEGIN
        SET @MontoSaldarHoy = 0.00;
    END
    ELSE IF @DiasDesdeVencimiento <= 5
    BEGIN
        -- Dentro de los 5 días de gracia: solo capital pendiente
        SET @MontoSaldarHoy = @CapitalBalance;
    END
    ELSE
    BEGIN
        -- Pasados los 5 días de gracia: Capital pendiente * (1 + Tasa / 100)
        SET @MontoSaldarHoy = ROUND(@CapitalBalance * (1.0 + (@TasaInteres / 100.0)), 2);
    END


    -- =====================================================================================
    -- RS 1: ENCABEZADO + 4 BLOQUES DE RESUMEN + PROYECCION CANCELACION
    -- =====================================================================================
    SELECT
        -- Identificacion
        @numeroCxc                  AS numeroPrestamo,
        @IdCliente                  AS idCliente,
        @NombreCliente              AS nombreCliente,
        CAST(@FechaPrestamo AS DATE)AS fechaPrestamo,
        GETDATE()                   AS fechaConsulta,
        @TasaInteres                AS tasaInteres,
        @EstadoPrestamo             AS estado,
        'PRESTAMO #' + @numeroCxc + ISNULL(' REF: ' + @Referencia, '') AS tipoPrestamo,
        @UsuarioCreador             AS creador,

        -- Bloque 1: INICIAL
        @CapitalInicial             AS capitalInicial,
        @InteresInicial             AS interesInicial,
        @TotalInicial               AS totalInicial,

        -- Bloque 2: PAGADO
        @CapitalPagado              AS capitalPagado,
        @InteresPagado              AS interesPagado,
        @MoraPagada                 AS moraPagada,
        @TotalPagado                AS totalPagado,

        -- Bloque 3: BALANCE
        @CapitalBalance             AS capitalBalance,
        @InteresBalance             AS interesBalance,
        @MoraBalance                AS moraBalance,
        @TotalBalance               AS totalBalance,

        -- Bloque 4: VENCIDO
        @CapitalVencido             AS capitalVencido,
        @InteresVencido             AS interesVencido,
        @MoraVencida                AS moraVencida,
        @TotalVencido               AS totalVencido,

        -- Bloque 5: PROYECCIÓN SALDAR HOY
        @MontoSaldarHoy             AS montoSaldarHoy,
        @DiasDesdeVencimiento       AS diasDesdeVencimiento,
        @UltimoVencimientoPasado    AS ultimoVencimiento,

        -- Metadata requerida por el backend Pydantic
        @CuotasVencidas             AS cuotasVencidas;


    -- =====================================================================================
    -- RS 2: TABLA DE CUOTAS
    -- =====================================================================================
    IF EXISTS (SELECT 1 FROM dbsolonegocios.dbo.tb_detalle_prestamos WHERE dp_id_prestamos = @idPrestamoInt)
    BEGIN
        SELECT
            dp.dp_num_cuotas                                  AS numCuota,
            CAST(dp.dp_id AS VARCHAR(50))                     AS idCuota,
            CAST(dp.dp_fecha_venc AS DATE)                    AS fecha,
            CAST(dp.dp_saldo_capital + dp.dp_saldo_interes AS DECIMAL(18,2)) AS balance,
            CAST(dp.dp_capital AS DECIMAL(18,2))             AS capital,
            CAST(dp.dp_interes AS DECIMAL(18,2))             AS interes,
            CAST(dp.dp_mora AS DECIMAL(18,2))                AS mora,
            CASE
                WHEN dp.dp_estado = 2 THEN 'PAGADA'
                WHEN CAST(dp.dp_fecha_venc AS DATE) < @Hoy AND (dp.dp_saldo_capital + dp.dp_saldo_interes) > 0 THEN 'ATRASADA'
                ELSE 'PENDIENTE'
            END AS estado,
            CASE
                WHEN dp.dp_estado = 2 THEN 'PAGADA'
                WHEN CAST(dp.dp_fecha_venc AS DATE) < @Hoy AND (dp.dp_saldo_capital + dp.dp_saldo_interes) > 0 THEN 'ATRASADA'
                ELSE 'PENDIENTE'
            END AS estadoCuota
        FROM dbsolonegocios.dbo.tb_detalle_prestamos dp
        WHERE dp.dp_id_prestamos = @idPrestamoInt
          AND dp_estado <> 0
        ORDER BY dp.dp_num_cuotas;
    END
    ELSE
    BEGIN
        -- Fallback si no hubiese detalle cuota a cuota
        SELECT 1 AS numCuota, '1' AS idCuota, CAST(@FechaPrestamo AS DATE) AS fecha,
               @TotalBalance AS balance, @CapitalInicial AS capital, @InteresInicial AS interes, 0.00 AS mora, 
               @EstadoPrestamo AS estado, @EstadoPrestamo AS estadoCuota;
    END


    -- =====================================================================================
    -- RS 3: HISTORIAL DE PAGOS (RECIBOS)
    -- =====================================================================================
    SELECT
        CAST(rp.rp_id_recibo AS VARCHAR(20))               AS numeroPago,
        CAST(rp.rp_fecha AS DATE)                          AS fecha,
        CAST(rp.rp_total_pagado AS DECIMAL(18,2))          AS totalPagado,
        CAST(rp.rp_capital AS DECIMAL(18,2))               AS capital,
        CAST(rp.rp_interes AS DECIMAL(18,2))               AS interes,
        CAST(rp.rp_mora AS DECIMAL(18,2))                  AS mora
    FROM dbsolonegocios.dbo.tb_recibo_pagos rp
    WHERE rp.rp_id_prestamo = @idPrestamoInt
      AND rp.rp_estado = 1
    ORDER BY rp.rp_fecha DESC, rp.rp_id_recibo DESC;


    -- =====================================================================================
    -- RS 4: CONTEOS
    -- =====================================================================================
    SELECT
        (SELECT COUNT(*) FROM dbsolonegocios.dbo.tb_detalle_prestamos WHERE dp_id_prestamos = @idPrestamoInt AND dp_estado <> 0) AS totalCuotas,
        (SELECT COUNT(*) FROM dbsolonegocios.dbo.tb_recibo_pagos WHERE rp_id_prestamo = @idPrestamoInt AND rp_estado = 1) AS totalRecibos;

END
GO

GO

-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- SCRIPT: 04_sp_ClientesIntelligence.sql
-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- =========================================================================================
-- SP: cxcClientesIntelligence (v7 - Fix Conteo Reenganchados, Paginación y Filtro de Fechas)
-- =========================================================================================
USE Financiera
GO

IF OBJECT_ID('dbo.cxcClientesIntelligence', 'P') IS NOT NULL
    DROP PROCEDURE dbo.cxcClientesIntelligence
GO

CREATE PROCEDURE dbo.cxcClientesIntelligence
    @fechaDesde       DATE         = NULL,
    @fechaHasta       DATE         = NULL,
    @empresa          VARCHAR(200) = NULL,
    @estado           VARCHAR(30)  = NULL,
    @busqueda         VARCHAR(200) = NULL,
    @oficina          VARCHAR(100) = NULL,
    @creador          VARCHAR(100) = NULL,
    @pagina           INT          = 1,
    @porPagina        INT          = 25,
    @tipoCliente      VARCHAR(20)  = 'ACTIVO',
    @ordenarPor       VARCHAR(50)  = 'fecha',
    @ordenDireccion   VARCHAR(10)  = 'DESC',
    @tipoFecha        VARCHAR(20)  = 'PRESTAMO' -- 'PRESTAMO' | 'INGRESO' | 'TODAS'
AS
BEGIN
    SET NOCOUNT ON;

    SET @pagina         = ISNULL(@pagina, 1);
    SET @porPagina      = ISNULL(@porPagina, 25);
    SET @tipoCliente    = UPPER(ISNULL(NULLIF(RTRIM(LTRIM(@tipoCliente)), ''), 'ACTIVO'));
    SET @estado         = UPPER(ISNULL(NULLIF(RTRIM(LTRIM(@estado)), ''), ''));
    SET @ordenarPor     = LOWER(ISNULL(NULLIF(RTRIM(LTRIM(@ordenarPor)), ''), 'fecha'));
    SET @ordenDireccion = UPPER(ISNULL(NULLIF(RTRIM(LTRIM(@ordenDireccion)), ''), 'DESC'));
    SET @tipoFecha      = UPPER(ISNULL(NULLIF(RTRIM(LTRIM(@tipoFecha)), ''), 'PRESTAMO'));

    IF @ordenDireccion NOT IN ('ASC', 'DESC')
        SET @ordenDireccion = 'DESC';

    DECLARE @offset INT  = (@pagina - 1) * @porPagina;
    DECLARE @Hoy    DATE = CAST(GETDATE() AS DATE);

    -- ── Tabla temporal para clientes clasificados ────────────────────
    CREATE TABLE #Clasificados (
        idCliente           INT,
        nombreCompleto      VARCHAR(200),
        cedula              VARCHAR(30),
        telefono            VARCHAR(30),
        correo              VARCHAR(100),
        direccion           VARCHAR(500),
        oficina             VARCHAR(100),
        fechaRegistro       DATE,
        idEmpresa           INT,
        empresa             VARCHAR(200),
        cargoEmpresa        VARCHAR(100),
        fechaIngresoEmpresa DATE,
        salario             DECIMAL(18,2),
        creador             VARCHAR(100),
        supervisor          VARCHAR(100),
        sexo                VARCHAR(5),
        esProblematico      BIT,
        banco               VARCHAR(100),
        cuentaBancaria      VARCHAR(50),
        totalPrestamos      INT,
        prestamosActivos    INT,
        primerPrestamo      DATETIME,
        ultimoPrestamo      DATETIME,
        montoHistorico      DECIMAL(18,2),
        numeroPrestamo      VARCHAR(50),
        montoActual         DECIMAL(18,2),
        tasa                FLOAT,
        fechaPrestamo       DATETIME,
        vencimiento         DATETIME,
        capitalPagado       DECIMAL(18,2),
        balanceActual       DECIMAL(18,2),
        balanceCapital      DECIMAL(18,2),
        ultimoVencimiento   DATETIME,
        montoSaldarHoy      DECIMAL(18,2),
        clasificacion       VARCHAR(20),
        estadoCartera       VARCHAR(20),
        tipoHistorial       VARCHAR(20),
        estadoFinanciero    VARCHAR(20),
        -- Referencias Personales
        nombreRef1          VARCHAR(200),
        parentescoRef1      VARCHAR(50),
        telRef1             VARCHAR(50),
        dirRef1             VARCHAR(300),
        nombreRef2          VARCHAR(200),
        parentescoRef2      VARCHAR(50),
        telRef2             VARCHAR(50),
        dirRef2             VARCHAR(300)
    );

    -- ── Consultar clientes con lógica de préstamo principal ─────────
    ;WITH PrestamosCliente AS (
        SELECT 
            p.pr_id_cliente,
            p.pr_id_prestamos,
            p.pr_id_solicitud,
            p.pr_monto,
            p.pr_tasa_interes,
            p.pr_fecha,
            p.pr_fecha_venc,
            p.pr_balance,
            p.pr_estado,
            p.pr_operador,
            CASE 
                WHEN p.pr_estado = 1 AND ISNULL(p.pr_balance, 0) > 0 THEN 1 
                ELSE 0 
            END AS esActivoConBalance,
            ROW_NUMBER() OVER (
                PARTITION BY p.pr_id_cliente 
                ORDER BY 
                    CASE WHEN p.pr_estado = 1 AND ISNULL(p.pr_balance, 0) > 0 THEN 0 ELSE 1 END,
                    p.pr_fecha DESC, 
                    p.pr_id_prestamos DESC
            ) AS rn
        FROM dbsolonegocios.dbo.tb_prestamos p
    ),
    PrestamoPrincipal AS (
        SELECT * FROM PrestamosCliente WHERE rn = 1
    ),
    ConteoHistorico AS (
        SELECT
            pr.pr_id_cliente,
            COUNT(*)                                                                              AS totalPrestamos,
            SUM(CASE WHEN pr.pr_estado = 1 AND ISNULL(pr.pr_balance, 0) > 0 THEN 1 ELSE 0 END)   AS prestamosActivos,
            MIN(pr.pr_fecha)                                                                      AS primerPrestamo,
            MAX(pr.pr_fecha)                                                                      AS ultimoPrestamo,
            SUM(CAST(pr.pr_monto AS DECIMAL(18,2)))                                              AS montoHistorico
        FROM dbsolonegocios.dbo.tb_prestamos pr
        GROUP BY pr.pr_id_cliente
    ),
    PagosPorPrestamo AS (
        SELECT 
            rp.rp_id_prestamo,
            SUM(rp.rp_capital) AS capitalPagado
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp
        WHERE rp.rp_estado = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
        GROUP BY rp.rp_id_prestamo
    ),
    BalancesCuotas AS (
        SELECT
            dp.dp_id_prestamos,
            SUM(dp.dp_saldo_capital) AS balanceCapital,
            SUM(dp.dp_saldo_capital + dp.dp_saldo_interes) AS balanceTotalDetalle,
            SUM(CASE WHEN dp.dp_estado = 1 AND DATEDIFF(day, dp.dp_fecha_venc, @Hoy) > 5 AND (dp.dp_saldo_capital + dp.dp_saldo_interes) > 0 THEN 1 ELSE 0 END) AS cuotasEnMoraReal
        FROM dbsolonegocios.dbo.tb_detalle_prestamos dp
        WHERE dp.dp_estado = 1
        GROUP BY dp.dp_id_prestamos
    ),
    UltimoVencimientoCuota AS (
        SELECT
            dp2.dp_id_prestamos,
            MAX(dp2.dp_fecha_venc) AS ultimoVencimiento
        FROM dbsolonegocios.dbo.tb_detalle_prestamos dp2
        WHERE dp2.dp_estado <> 0 
          AND CAST(dp2.dp_fecha_venc AS DATE) <= @Hoy
        GROUP BY dp2.dp_id_prestamos
    )
    INSERT INTO #Clasificados
    SELECT
        vc.CODIGO,
        vc.NOMBRE_COMPLETO,
        vc.IDENTIDAD,
        vc.CELULAR,
        vc.CORREO,
        vc.DIRECCION,
        vc.OFICINA,
        CAST(ISNULL(tc.cl_fecha_reg, TRY_CAST(vc.FECHA_REGISTRO AS DATE)) AS DATE),
        vc.ID_EMPRESA,
        vc.EMPRESA,
        vc.POSICION,
        TRY_CAST(vc.FECHA_INGRESO AS DATE),
        CAST(ISNULL(vc.SALARIO, 0) AS DECIMAL(18,2)),

        -- Creador del Caso en Infycredit / Solicitud / Préstamo
        COALESCE(
            NULLIF(NULLIF(sol.s_operador, '0'), ''),
            NULLIF(NULLIF(sol2.s_operador, '0'), ''),
            NULLIF(NULLIF(pa.pr_operador, '0'), ''),
            NULLIF(NULLIF(tc.cl_operador, '0'), ''),
            NULLIF(NULLIF(vc.OPERADOR, '0'), ''),
            NULLIF(NULLIF(vc.GESTOR, '0'), ''),
            ''
        ) AS creador,

        vc.SUPERVISOR,
        vc.SEXO,
        vc.PROBLEMATICO,
        vc.BANCO,
        vc.CUENTA,
        
        -- Conteo de préstamos en el historial del cliente
        ISNULL(cp.totalPrestamos, 1),
        ISNULL(cp.prestamosActivos, 0),
        cp.primerPrestamo,
        cp.ultimoPrestamo,
        ISNULL(cp.montoHistorico, 0),

        -- Préstamo principal
        CAST(pa.pr_id_prestamos AS VARCHAR(50)),
        ISNULL(pa.pr_monto, 0),
        CAST(ISNULL(pa.pr_tasa_interes, 0) AS FLOAT),
        pa.pr_fecha,
        pa.pr_fecha_venc,
        ISNULL(pag.capitalPagado, 0),

        -- Balance Actual Total
        COALESCE(NULLIF(pa.pr_balance, 0), NULLIF(bc.balanceTotalDetalle, 0), 0.00) AS balanceActual,

        -- Balance de capital pendiente para saldar
        COALESCE(NULLIF(bc.balanceCapital, 0), NULLIF(pa.pr_monto - ISNULL(pag.capitalPagado, 0), 0), pa.pr_balance, 0.00) AS balanceCapital,
        uvc.ultimoVencimiento,

        -- Monto para Saldar Hoy (Regla de 5 días de gracia tras fecha de cuota)
        CASE 
            WHEN pa.pr_id_prestamos IS NULL OR (ISNULL(pa.pr_balance, 0) <= 0 AND ISNULL(bc.balanceCapital, 0) <= 0)
                THEN 0.00
            WHEN DATEDIFF(day, ISNULL(uvc.ultimoVencimiento, pa.pr_fecha), @Hoy) <= 5
                THEN COALESCE(NULLIF(bc.balanceCapital, 0), NULLIF(pa.pr_monto - ISNULL(pag.capitalPagado, 0), 0), pa.pr_balance, 0.00)
            ELSE 
                ROUND(COALESCE(NULLIF(bc.balanceCapital, 0), NULLIF(pa.pr_monto - ISNULL(pag.capitalPagado, 0), 0), pa.pr_balance, 0.00) * (1.0 + (ISNULL(pa.pr_tasa_interes, 0) / 100.0)), 2)
        END AS montoSaldarHoy,

        -- Clasificación visual para etiqueta
        CASE
            WHEN pa.esActivoConBalance = 0 AND ISNULL(bc.balanceCapital, 0) <= 0
                THEN 'CANCELADO'
            WHEN vc.PROBLEMATICO = 1
                THEN 'PROBLEMATICO'
            WHEN ISNULL(bc.cuotasEnMoraReal, 0) > 0
                THEN 'EN MORA'
            WHEN ISNULL(cp.totalPrestamos, 1) <= 1
                THEN 'NUEVO'
            ELSE 'REENGANCHADO'
        END AS clasificacion,

        -- Condición general de cartera
        CASE 
            WHEN pa.esActivoConBalance = 1 OR ISNULL(bc.balanceCapital, 0) > 0 THEN 'ACTIVO' 
            ELSE 'CANCELADO' 
        END AS estadoCartera,

        -- Dimension 1: Historial
        CASE WHEN ISNULL(cp.totalPrestamos, 1) > 1 THEN 'REENGANCHADO' ELSE 'NUEVO' END AS tipoHistorial,

        -- Dimension 2: Estado Financiero
        CASE 
            WHEN pa.esActivoConBalance = 0 AND ISNULL(bc.balanceCapital, 0) <= 0 THEN 'CANCELADO'
            WHEN vc.PROBLEMATICO = 1 THEN 'PROBLEMATICO'
            WHEN ISNULL(bc.cuotasEnMoraReal, 0) > 0 THEN 'EN MORA'
            ELSE 'AL DIA'
        END AS estadoFinanciero,

        -- Referencias Personales
        vc.NOMBRE_REFERENCIA_UNO,
        CAST(vc.TIPO_REFENRECIA_UNO AS VARCHAR(50)),
        vc.TEL_REFERENCIA_UNO,
        vc.DIR_REFERENCIA_UNO,
        vc.NOMBRE_REFERENCIA_DOS,
        CAST(vc.TIPO_REFERENCIA_DOS AS VARCHAR(50)),
        vc.TEL_REFERENCIA_DOS,
        vc.DIR_REFERENCIA_DOS

    FROM (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY CODIGO ORDER BY ID_OFICINA) AS rn_vc
        FROM dbsolonegocios.dbo.vw_datos_clientes
    ) vc
    LEFT JOIN (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY cl_id_cliente ORDER BY cl_id_oficina) AS rn_tc
        FROM dbsolonegocios.dbo.tb_clientes
    ) tc ON tc.cl_id_cliente = vc.CODIGO AND tc.rn_tc = 1
    INNER JOIN PrestamoPrincipal pa ON pa.pr_id_cliente = vc.CODIGO
    LEFT JOIN dbsolonegocios.dbo.tb_solicitud_prestamos sol ON sol.s_id_solicitud = pa.pr_id_solicitud AND sol.s_id_cliente = vc.CODIGO
    OUTER APPLY (
        SELECT TOP 1 s2.s_operador
        FROM dbsolonegocios.dbo.tb_solicitud_prestamos s2
        WHERE s2.s_id_cliente = vc.CODIGO
          AND s2.s_operador IS NOT NULL AND s2.s_operador <> '' AND s2.s_operador <> '0'
        ORDER BY s2.s_fecha_registro DESC, s2.s_id_solicitud DESC
    ) sol2
    LEFT JOIN ConteoHistorico cp ON cp.pr_id_cliente = vc.CODIGO
    LEFT JOIN PagosPorPrestamo pag ON pag.rp_id_prestamo = pa.pr_id_prestamos
    LEFT JOIN BalancesCuotas bc ON bc.dp_id_prestamos = pa.pr_id_prestamos
    LEFT JOIN UltimoVencimientoCuota uvc ON uvc.dp_id_prestamos = pa.pr_id_prestamos
    WHERE
        vc.rn_vc = 1
        AND (
            (@tipoCliente = 'ACTIVO'    AND (pa.esActivoConBalance = 1 OR ISNULL(bc.balanceCapital, 0) > 0))
            OR (@tipoCliente = 'CANCELADO' AND pa.esActivoConBalance = 0 AND ISNULL(bc.balanceCapital, 0) <= 0)
            OR (@tipoCliente = 'TODOS')
        )
        -- Filtro de fechas desacoplado y seguro
        AND (
            @tipoFecha = 'TODAS'
            OR (@tipoFecha = 'INGRESO' 
                AND (@fechaDesde IS NULL OR ISNULL(tc.cl_fecha_reg, TRY_CAST(vc.FECHA_REGISTRO AS DATE)) >= @fechaDesde)
                AND (@fechaHasta IS NULL OR ISNULL(tc.cl_fecha_reg, TRY_CAST(vc.FECHA_REGISTRO AS DATE)) <= @fechaHasta)
            )
            OR (@tipoFecha = 'PRESTAMO'
                AND (@fechaDesde IS NULL OR CAST(pa.pr_fecha AS DATE) >= @fechaDesde)
                AND (@fechaHasta IS NULL OR CAST(pa.pr_fecha AS DATE) <= @fechaHasta)
            )
        )
        AND (@empresa IS NULL OR vc.EMPRESA LIKE '%' + @empresa + '%')
        AND (@oficina  IS NULL OR vc.OFICINA = @oficina)
        AND (@creador  IS NULL 
             OR sol.s_operador LIKE '%' + @creador + '%'
             OR pa.pr_operador LIKE '%' + @creador + '%'
             OR tc.cl_operador LIKE '%' + @creador + '%'
             OR vc.OPERADOR    LIKE '%' + @creador + '%')
        AND (@busqueda IS NULL
             OR vc.NOMBRE_COMPLETO LIKE '%' + @busqueda + '%'
             OR vc.IDENTIDAD        LIKE '%' + @busqueda + '%'
             OR vc.CELULAR          LIKE '%' + @busqueda + '%'
             OR CAST(pa.pr_id_prestamos AS VARCHAR(50)) LIKE '%' + @busqueda + '%');

    -- ── Métricas Globales del Universo (para las tarjetas KPI fijas) ──
    DECLARE @GlobalTotal INT, @GlobalNuevos INT, @GlobalReenganchados INT, @GlobalEnMora INT, 
            @GlobalProblematicos INT, @GlobalAlDia INT, @GlobalCancelados INT,
            @GlobalMonto DECIMAL(18,2), @GlobalBalance DECIMAL(18,2);

    SELECT 
        @GlobalTotal         = COUNT(*),
        @GlobalNuevos        = ISNULL(SUM(CASE WHEN tipoHistorial = 'NUEVO'        THEN 1 ELSE 0 END), 0),
        @GlobalReenganchados = ISNULL(SUM(CASE WHEN tipoHistorial = 'REENGANCHADO' THEN 1 ELSE 0 END), 0),
        @GlobalEnMora        = ISNULL(SUM(CASE WHEN estadoFinanciero = 'EN MORA'   THEN 1 ELSE 0 END), 0),
        @GlobalProblematicos = ISNULL(SUM(CASE WHEN esProblematico = 1             THEN 1 ELSE 0 END), 0),
        @GlobalAlDia         = ISNULL(SUM(CASE WHEN estadoFinanciero = 'AL DIA'    THEN 1 ELSE 0 END), 0),
        @GlobalCancelados    = ISNULL(SUM(CASE WHEN estadoCartera = 'CANCELADO'    THEN 1 ELSE 0 END), 0),
        @GlobalMonto         = ISNULL(SUM(montoActual), 0),
        @GlobalBalance       = ISNULL(SUM(balanceActual), 0)
    FROM #Clasificados;

    -- Aplicar filtro de chip rápido (@estado: NUEVO, REENGANCHADO, EN MORA, AL DIA, etc.)
    IF @estado = 'NUEVO'
        DELETE FROM #Clasificados WHERE tipoHistorial <> 'NUEVO';
    ELSE IF @estado = 'REENGANCHADO'
        DELETE FROM #Clasificados WHERE tipoHistorial <> 'REENGANCHADO';
    ELSE IF @estado = 'EN MORA'
        DELETE FROM #Clasificados WHERE estadoFinanciero <> 'EN MORA';
    ELSE IF @estado = 'AL DIA'
        DELETE FROM #Clasificados WHERE estadoFinanciero <> 'AL DIA';
    ELSE IF @estado = 'PROBLEMATICO'
        DELETE FROM #Clasificados WHERE esProblematico <> 1;
    ELSE IF @estado = 'CANCELADO'
        DELETE FROM #Clasificados WHERE estadoCartera <> 'CANCELADO';

    DECLARE @TotalFiltrados INT;
    SELECT @TotalFiltrados = COUNT(*) FROM #Clasificados;

    -- ── RS 1: KPIs Globales y Totales Filtrados Sincronizados ────────
    SELECT
        @GlobalTotal                                                          AS totalClientesGlobal,
        @TotalFiltrados                                                       AS totalClientes,  -- Conteo real para paginación y cabecera
        @TotalFiltrados                                                       AS totalFiltrados,
        @GlobalNuevos                                                         AS nuevos,
        @GlobalReenganchados                                                  AS reenganchados,
        @GlobalEnMora                                                         AS enMora,
        @GlobalProblematicos                                                  AS problematicos,
        @GlobalAlDia                                                          AS alDia,
        @GlobalCancelados                                                     AS cancelados,
        @GlobalMonto                                                          AS montoTotalCartera,
        @GlobalBalance                                                        AS balanceTotalPendiente,
        @pagina                                                               AS paginaActual,
        @porPagina                                                            AS porPagina,
        CAST(CEILING(CAST(@TotalFiltrados AS FLOAT) / @porPagina) AS INT)     AS totalPaginas;

    -- ── RS 2: Lista Paginada de Clientes (con ordenamiento robusto) ────
    SELECT
        idCliente, nombreCompleto, cedula, telefono, correo,
        oficina, fechaRegistro, empresa, cargoEmpresa, salario,
        creador, sexo, esProblematico, banco, cuentaBancaria,
        totalPrestamos, prestamosActivos,
        primerPrestamo, ultimoPrestamo, montoHistorico,
        numeroPrestamo, montoActual, tasa, fechaPrestamo,
        vencimiento, capitalPagado, balanceActual, balanceCapital,
        montoSaldarHoy, clasificacion, estadoCartera,
        nombreRef1, parentescoRef1, telRef1, dirRef1,
        nombreRef2, parentescoRef2, telRef2, dirRef2
    FROM #Clasificados
    ORDER BY
        -- Orden ASCENDENTE
        CASE WHEN @ordenDireccion = 'ASC' AND @ordenarPor = 'cliente'        THEN nombreCompleto END ASC,
        CASE WHEN @ordenDireccion = 'ASC' AND @ordenarPor = 'cedula'         THEN cedula END ASC,
        CASE WHEN @ordenDireccion = 'ASC' AND @ordenarPor = 'empresa'        THEN empresa END ASC,
        CASE WHEN @ordenDireccion = 'ASC' AND @ordenarPor = 'prestamo'       THEN TRY_CAST(numeroPrestamo AS BIGINT) END ASC,
        CASE WHEN @ordenDireccion = 'ASC' AND @ordenarPor = 'balance'        THEN balanceActual END ASC,
        CASE WHEN @ordenDireccion = 'ASC' AND @ordenarPor = 'creador'        THEN creador END ASC,
        CASE WHEN @ordenDireccion = 'ASC' AND (@ordenarPor = 'fecha' OR @ordenarPor = 'fecharegistro') THEN fechaRegistro END ASC,
        CASE WHEN @ordenDireccion = 'ASC' AND @ordenarPor = 'montosaldar'    THEN montoSaldarHoy END ASC,

        -- Orden DESCENDENTE
        CASE WHEN @ordenDireccion = 'DESC' AND @ordenarPor = 'cliente'       THEN nombreCompleto END DESC,
        CASE WHEN @ordenDireccion = 'DESC' AND @ordenarPor = 'cedula'        THEN cedula END DESC,
        CASE WHEN @ordenDireccion = 'DESC' AND @ordenarPor = 'empresa'       THEN empresa END DESC,
        CASE WHEN @ordenDireccion = 'DESC' AND @ordenarPor = 'prestamo'      THEN TRY_CAST(numeroPrestamo AS BIGINT) END DESC,
        CASE WHEN @ordenDireccion = 'DESC' AND @ordenarPor = 'balance'       THEN balanceActual END DESC,
        CASE WHEN @ordenDireccion = 'DESC' AND @ordenarPor = 'creador'       THEN creador END DESC,
        CASE WHEN @ordenDireccion = 'DESC' AND (@ordenarPor = 'fecha' OR @ordenarPor = 'fecharegistro') THEN fechaRegistro END DESC,
        CASE WHEN @ordenDireccion = 'DESC' AND @ordenarPor = 'montosaldar'   THEN montoSaldarHoy END DESC,

        idCliente DESC
    OFFSET @offset ROWS FETCH NEXT @porPagina ROWS ONLY;

    -- ── RS 3: Top 15 Empresas ────────────────────────────────────────
    SELECT TOP 15
        ISNULL(empresa, 'Sin Empresa')                                      AS empresa,
        COUNT(*)                                                            AS totalClientes,
        ISNULL(SUM(CASE WHEN tipoHistorial='NUEVO'        THEN 1 ELSE 0 END), 0) AS nuevos,
        ISNULL(SUM(CASE WHEN tipoHistorial='REENGANCHADO' THEN 1 ELSE 0 END), 0) AS reenganchados,
        ISNULL(SUM(CASE WHEN estadoFinanciero='EN MORA'   THEN 1 ELSE 0 END), 0) AS enMora,
        ISNULL(SUM(balanceActual), 0)                                       AS cartera
    FROM #Clasificados
    GROUP BY empresa
    ORDER BY totalClientes DESC;

    -- ── RS 4: Dropdowns únicos ───────────────────────────────────────
    SELECT DISTINCT oficina FROM #Clasificados
    WHERE oficina IS NOT NULL ORDER BY oficina;

    DROP TABLE #Clasificados;
END
GO

GO

-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- SCRIPT: 06_sp_Actualizacion_Interfaces.sql
-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- =========================================================================================
-- SP: ACTUALIZACION DE PROCEDIMIENTOS DE INTERFAZ DE TAREAS WINDOWS (Solonegocios -> Financiera)
-- =========================================================================================
-- Propósito:
--   Mejorar los procedimientos de transferencia de datos que ejecuta el Programador de Tareas
--   de Windows entre SoloNegocios y Financiera:
--   1. IntfPrestamo2Cxc:
--      - Une tb_detalle_prestamos por (dp_id_oficina, dp_id_prestamos).
--      - Sincroniza cancelaciones/saldos de préstamos (Cancelado = 1) evaluando pr_estado <> 1,
--        reenganches (tb_reenganche) o ausencia de cuotas pendientes con saldo > 0 (dp_estado = 1).
--   2. IntfReciboPrestamo2Cxc:
--      - Excluye Notas de Crédito internas de reenganche (rp_forma_pago = 'N.CREDITO' y tb_notas_credito)
--        para evitar transferir liquidaciones internas como recibos de efectivo (RC).
--      - Resuelve el idCliente desde el préstamo FT cuando rp_id_cliente venga nulo (pagos automáticos).
--   3. IntfSincronizarInteresMora2Cxc:
--      - Asocia la Referencia (GUID del FT) en las ND de Interés y Mora, excluyendo Notas de Crédito.
-- =========================================================================================
USE Financiera
GO

-- -----------------------------------------------------------------------------------------
-- 1. MEJORA A IntfPrestamo2Cxc
-- -----------------------------------------------------------------------------------------
IF OBJECT_ID('dbo.IntfPrestamo2Cxc', 'P') IS NOT NULL
    DROP PROCEDURE dbo.IntfPrestamo2Cxc
GO

CREATE PROCEDURE [dbo].[IntfPrestamo2Cxc]
AS
BEGIN
    SET NOCOUNT ON;

    -- 1. INSERTAR NUEVOS PRESTAMOS
    INSERT INTO dbo.Cxc (
        idCxc, Cxc, idCliente, idTipoDocumento, Valor, Fecha, Concepto, idCxcTipo, esCredito, Cancelado, Cliente, Usuario, 
        idDocumento, Descuento, Condicion, Vencimiento, idMoneda, Tasa, recibido, PendValidacion, PendEnvioEcf, StatusEcf
    )
    SELECT
        NEWID(),
        CAST(P.pr_id_prestamos AS VARCHAR(16)),
        P.pr_id_cliente,
        'FT',
        ISNULL(D.CapitalOriginal, ISNULL(P.pr_monto, 0)),
        P.pr_fecha,
        'PRESTAMO #' + CAST(P.pr_id_prestamos AS VARCHAR(20)) + ISNULL(' REF: ' + P.pr_referencia,''),
        -1,
        0,
        CASE WHEN P.pr_estado = 1 AND ISNULL(D.BalanceActual, 0) > 0 THEN 0 ELSE 1 END,
        C.Cliente,
        P.pr_operador,
        CAST(P.pr_id_prestamos AS VARCHAR(20)),
        0,
        30,
        ISNULL(D.FechaVencimiento, P.pr_fecha_venc),
        1,
        CASE WHEN ISNULL(P.pr_tasa_interes,0)=0 THEN 1 ELSE CAST(P.pr_tasa_interes AS FLOAT) END,
        0,
        0,
        0,
        'PENDIENTE'
    FROM dbsolonegocios.dbo.tb_prestamos P
    INNER JOIN (
        SELECT
            dp_id_oficina,
            dp_id_prestamos,
            SUM(dp_capital) AS CapitalOriginal,
            SUM(CASE WHEN dp_estado = 1 THEN dp_saldo_capital ELSE 0 END) AS BalanceActual,
            MAX(dp_fecha_venc) AS FechaVencimiento
        FROM dbsolonegocios.dbo.tb_detalle_prestamos
        WHERE dp_estado <> 0
        GROUP BY dp_id_oficina, dp_id_prestamos
    ) D ON D.dp_id_prestamos = P.pr_id_prestamos AND D.dp_id_oficina = P.pr_id_oficina
    INNER JOIN dbo.Cliente C ON C.idCliente = P.pr_id_cliente
    WHERE ISNULL(P.pr_estado, 0) <> 0
      AND NOT EXISTS (
          SELECT 1 FROM dbo.Cxc X WHERE X.idDocumento = CAST(P.pr_id_prestamos AS VARCHAR(20)) AND X.idTipoDocumento = 'FT'
      );

    -- 2. SINCRONIZAR ESTADO DE PRESTAMOS QUE YA FUERON SALDADOS, REENGANCHADOS O CANCELADOS EN SOLONEGOCIOS
    UPDATE c
    SET c.Cancelado = 1
    FROM dbo.Cxc c
    INNER JOIN dbsolonegocios.dbo.tb_prestamos p 
        ON (c.idDocumento = CAST(p.pr_id_prestamos AS VARCHAR(20)) OR c.Cxc = CAST(p.pr_id_prestamos AS VARCHAR(16)))
        AND c.idTipoDocumento = 'FT'
    WHERE c.Cancelado = 0
      AND (
          p.pr_estado <> 1
          OR EXISTS (
              SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg
              WHERE rg.rg_id_prestamo = p.pr_id_prestamos AND rg.rg_id_oficina = p.pr_id_oficina
          )
          OR NOT EXISTS (
              SELECT 1 FROM dbsolonegocios.dbo.tb_detalle_prestamos dp
              WHERE dp.dp_id_prestamos = p.pr_id_prestamos
                AND dp.dp_id_oficina = p.pr_id_oficina
                AND dp.dp_estado = 1
                AND dp.dp_saldo_capital > 0
          )
      );

    -- 3. REACTIVAR SI UN PRESTAMO TIENE SALDO ACTIVO VIGENTE REAL
    UPDATE c
    SET c.Cancelado = 0
    FROM dbo.Cxc c
    INNER JOIN dbsolonegocios.dbo.tb_prestamos p 
        ON (c.idDocumento = CAST(p.pr_id_prestamos AS VARCHAR(20)) OR c.Cxc = CAST(p.pr_id_prestamos AS VARCHAR(16)))
        AND c.idTipoDocumento = 'FT'
    WHERE c.Cancelado = 1
      AND p.pr_estado = 1
      AND NOT EXISTS (
          SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg
          WHERE rg.rg_id_prestamo = p.pr_id_prestamos AND rg.rg_id_oficina = p.pr_id_oficina
      )
      AND EXISTS (
          SELECT 1 FROM dbsolonegocios.dbo.tb_detalle_prestamos dp
          WHERE dp.dp_id_prestamos = p.pr_id_prestamos
            AND dp.dp_id_oficina = p.pr_id_oficina
            AND dp.dp_estado = 1
            AND dp.dp_saldo_capital > 0
      );
END
GO

-- -----------------------------------------------------------------------------------------
-- 2. MEJORA A IntfReciboPrestamo2Cxc
-- -----------------------------------------------------------------------------------------
IF OBJECT_ID('dbo.IntfReciboPrestamo2Cxc', 'P') IS NOT NULL
    DROP PROCEDURE dbo.IntfReciboPrestamo2Cxc
GO

CREATE PROCEDURE [dbo].[IntfReciboPrestamo2Cxc]
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.Cxc (
        idCxc, Cxc, idCliente, idTipoDocumento, Valor, Fecha, Concepto, idCxcTipo,
        esCredito, Cancelado, Referencia, Cliente, Usuario, idDocumento, Descuento,
        Condicion, idMoneda, Tasa, recibido, PendValidacion, PendEnvioEcf, StatusEcf
    )
    SELECT
        NEWID(),
        CAST(r.rp_id_recibo AS VARCHAR(16)),
        ISNULL(r.rp_id_cliente, f.idCliente),
        'RC',
        r.rp_total_pagado,
        r.rp_fecha,
        'PAGO PRESTAMO #' + CAST(r.rp_id_prestamo AS VARCHAR(20)),
        -2,
        1,
        CASE WHEN r.rp_estado <> 1 THEN 1 ELSE 0 END,
        f.idCxc,
        c.Cliente,
        r.rp_operador,
        CAST(r.rp_id_recibo AS VARCHAR(20)),
        0,
        0,
        1,
        ISNULL(f.Tasa, 1),
        1,
        0,
        0,
        'PENDIENTE'
    FROM dbsolonegocios.dbo.tb_recibo_pagos r
    INNER JOIN dbo.Cxc f
        ON f.idDocumento = CAST(r.rp_id_prestamo AS VARCHAR(20))
        AND f.idTipoDocumento = 'FT'
        AND f.idCxcTipo = -1
    INNER JOIN dbo.Cliente c
        ON c.idCliente = ISNULL(r.rp_id_cliente, f.idCliente)
    WHERE ISNULL(r.rp_total_pagado, 0) > 0
      AND ISNULL(r.rp_estado, 1) = 1
      AND UPPER(LTRIM(RTRIM(ISNULL(r.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
      AND ISNULL(r.rp_observacion, '') NOT LIKE '%Nota de Credito%'
      AND ISNULL(r.rp_observacion, '') NOT LIKE '%Reenganche%'
      AND NOT EXISTS (
          SELECT 1 FROM dbsolonegocios.dbo.tb_notas_credito nc
          WHERE nc.nc_recibo_pago = r.rp_id_recibo AND nc.nc_id_oficina = r.rp_id_oficina
      )
      AND NOT EXISTS (
          SELECT 1 FROM dbo.Cxc x
          WHERE x.idDocumento = CAST(r.rp_id_recibo AS VARCHAR(20))
            AND x.idTipoDocumento = 'RC'
      );
END
GO

-- -----------------------------------------------------------------------------------------
-- 3. MEJORA A IntfSincronizarInteresMora2Cxc
-- -----------------------------------------------------------------------------------------
IF OBJECT_ID('dbo.IntfSincronizarInteresMora2Cxc', 'P') IS NOT NULL
    DROP PROCEDURE dbo.IntfSincronizarInteresMora2Cxc
GO

CREATE PROCEDURE [dbo].[IntfSincronizarInteresMora2Cxc]
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    BEGIN TRY
        BEGIN TRANSACTION;

        DECLARE @idCxcTipo_Interes INT = 12;
        DECLARE @idCxcTipo_Mora INT = 13;

        -- 1. CREACIÓN DE NUEVAS NOTAS DE DÉBITO (INTERÉS Y MORA) CON VÍNCULO A LA FACTURA FT (Referencia = ft.idCxc)
        INSERT INTO dbo.Cxc (
            idCxc, Cxc, idCliente, idTipoDocumento, Valor, Fecha, Concepto, idCxcTipo, esCredito, Cancelado, Cliente, 
            Usuario, idDocumento, Descuento, Condicion, Vencimiento, idMoneda, Tasa, recibido, PendValidacion, PendEnvioEcf, StatusEcf, Referencia
        )
        SELECT 
            NEWID(), 'INT-' + CAST(rp.rp_id_recibo AS VARCHAR(20)), rc.idCliente, 'ND', rp.rp_interes, rp.rp_fecha, 
            'INTERESES DEL RECIBO #' + CAST(rp.rp_id_recibo AS VARCHAR(20)) + ' REF: PRESTAMO ' + CAST(rp.rp_id_prestamo AS VARCHAR(20)), 
            @idCxcTipo_Interes, 0, 0, rc.Cliente, rc.Usuario, 'INT-' + CAST(rp.rp_id_recibo AS VARCHAR(20)), 
            0, 30, rp.rp_fecha, 1, 1, 0, 0, 0, 'PENDIENTE', ft.idCxc
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp
        JOIN dbo.Cxc rc ON rc.idDocumento = CAST(rp.rp_id_recibo AS VARCHAR(20)) AND rc.idTipoDocumento = 'RC'
        LEFT JOIN dbo.Cxc ft ON (ft.idDocumento = CAST(rp.rp_id_prestamo AS VARCHAR(20)) OR ft.Cxc = CAST(rp.rp_id_prestamo AS VARCHAR(20))) AND ft.idTipoDocumento = 'FT'
        WHERE ISNULL(rp.rp_interes, 0) > 0 AND rp.rp_estado = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
          AND NOT EXISTS (SELECT 1 FROM dbo.Cxc nd WHERE nd.idDocumento = 'INT-' + CAST(rp.rp_id_recibo AS VARCHAR(20)) AND nd.idTipoDocumento = 'ND');

        INSERT INTO dbo.Cxc (
            idCxc, Cxc, idCliente, idTipoDocumento, Valor, Fecha, Concepto, idCxcTipo, esCredito, Cancelado, Cliente, 
            Usuario, idDocumento, Descuento, Condicion, Vencimiento, idMoneda, Tasa, recibido, PendValidacion, PendEnvioEcf, StatusEcf, Referencia
        )
        SELECT 
            NEWID(), 'MOR-' + CAST(rp.rp_id_recibo AS VARCHAR(20)), rc.idCliente, 'ND', rp.rp_mora, rp.rp_fecha, 
            'MORA DEL RECIBO #' + CAST(rp.rp_id_recibo AS VARCHAR(20)) + ' REF: PRESTAMO ' + CAST(rp.rp_id_prestamo AS VARCHAR(20)), 
            @idCxcTipo_Mora, 0, 0, rc.Cliente, rc.Usuario, 'MOR-' + CAST(rp.rp_id_recibo AS VARCHAR(20)), 
            0, 30, rp.rp_fecha, 1, 1, 0, 0, 0, 'PENDIENTE', ft.idCxc
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp
        JOIN dbo.Cxc rc ON rc.idDocumento = CAST(rp.rp_id_recibo AS VARCHAR(20)) AND rc.idTipoDocumento = 'RC'
        LEFT JOIN dbo.Cxc ft ON (ft.idDocumento = CAST(rp.rp_id_prestamo AS VARCHAR(20)) OR ft.Cxc = CAST(rp.rp_id_prestamo AS VARCHAR(20))) AND ft.idTipoDocumento = 'FT'
        WHERE ISNULL(rp.rp_mora, 0) > 0 AND rp.rp_estado = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
          AND NOT EXISTS (SELECT 1 FROM dbo.Cxc nd WHERE nd.idDocumento = 'MOR-' + CAST(rp.rp_id_recibo AS VARCHAR(20)) AND nd.idTipoDocumento = 'ND');

        -- 2. APLICACIÓN DE PAGOS (CxcDet)
        INSERT INTO dbo.CxcDet (idCxcDet, idCxc, idCxcDebito, Valor, Fecha, Descuento, Tasa, Referencia)
        SELECT NEWID(), rc.idCxc, nd.idCxc, rp.rp_interes, rc.Fecha, 0, rc.Tasa, 'APL. INTERES RECIBO #' + CAST(rp.rp_id_recibo AS VARCHAR(20))
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp
        JOIN dbo.Cxc rc ON rc.idDocumento = CAST(rp.rp_id_recibo AS VARCHAR(20)) AND rc.idTipoDocumento = 'RC'
        JOIN dbo.Cxc nd ON nd.idDocumento = 'INT-' + CAST(rp.rp_id_recibo AS VARCHAR(20)) AND nd.idTipoDocumento = 'ND'
        WHERE ISNULL(rp.rp_interes, 0) > 0 AND rp.rp_estado = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
          AND NOT EXISTS (SELECT 1 FROM dbo.CxcDet cd WHERE cd.idCxc = rc.idCxc AND cd.idCxcDebito = nd.idCxc);

        INSERT INTO dbo.CxcDet (idCxcDet, idCxc, idCxcDebito, Valor, Fecha, Descuento, Tasa, Referencia)
        SELECT NEWID(), rc.idCxc, nd.idCxc, rp.rp_mora, rc.Fecha, 0, rc.Tasa, 'APL. MORA RECIBO #' + CAST(rp.rp_id_recibo AS VARCHAR(20))
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp
        JOIN dbo.Cxc rc ON rc.idDocumento = CAST(rp.rp_id_recibo AS VARCHAR(20)) AND rc.idTipoDocumento = 'RC'
        JOIN dbo.Cxc nd ON nd.idDocumento = 'MOR-' + CAST(rp.rp_id_recibo AS VARCHAR(20)) AND nd.idTipoDocumento = 'ND'
        WHERE ISNULL(rp.rp_mora, 0) > 0 AND rp.rp_estado = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
          AND NOT EXISTS (SELECT 1 FROM dbo.CxcDet cd WHERE cd.idCxc = rc.idCxc AND cd.idCxcDebito = nd.idCxc);

        -- 3. GENERACIÓN DE CODIFICACIÓN CONTABLE AUTOMÁTICA
        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), nd.idCxc, '10105001', 1, nd.Valor, 'ASIENTO INTERES', 1, 'ND', nd.Fecha FROM dbo.Cxc nd 
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'INTERESES DEL RECIBO %' AND nd.idCxcTipo = @idCxcTipo_Interes
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WHERE cg.GUIDDocumento = nd.idCxc AND cg.DebCre = 1);

        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), nd.idCxc, '42401', 2, nd.Valor, 'ASIENTO INTERES', 1, 'ND', nd.Fecha FROM dbo.Cxc nd 
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'INTERESES DEL RECIBO %' AND nd.idCxcTipo = @idCxcTipo_Interes
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WHERE cg.GUIDDocumento = nd.idCxc AND cg.DebCre = 2);

        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), nd.idCxc, '10105002', 1, nd.Valor, 'ASIENTO MORA', 1, 'ND', nd.Fecha FROM dbo.Cxc nd 
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'MORA DEL RECIBO %' AND nd.idCxcTipo = @idCxcTipo_Mora
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WHERE cg.GUIDDocumento = nd.idCxc AND cg.DebCre = 1);

        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), nd.idCxc, '42501', 2, nd.Valor, 'ASIENTO MORA', 1, 'ND', nd.Fecha FROM dbo.Cxc nd 
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'MORA DEL RECIBO %' AND nd.idCxcTipo = @idCxcTipo_Mora
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WHERE cg.GUIDDocumento = nd.idCxc AND cg.DebCre = 2);

        -- RECLASIFICACIÓN DE APLICACIÓN
        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), cd.idCxcDet, '10102001', 1, cd.TotalAplicado, 'APLICACION INTERES', 1, 'AP', cd.Fecha 
        FROM dbo.CxcDet cd JOIN dbo.Cxc nd ON cd.idCxcDebito = nd.idCxc
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'INTERESES DEL RECIBO %'
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WHERE cg.GUIDDocumento = cd.idCxcDet AND cg.DebCre = 1);

        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), cd.idCxcDet, '10105001', 2, cd.TotalAplicado, 'APLICACION INTERES', 1, 'AP', cd.Fecha 
        FROM dbo.CxcDet cd JOIN dbo.Cxc nd ON cd.idCxcDebito = nd.idCxc
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'INTERESES DEL RECIBO %'
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WHERE cg.GUIDDocumento = cd.idCxcDet AND cg.DebCre = 2);

        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), cd.idCxcDet, '10102001', 1, cd.TotalAplicado, 'APLICACION MORA', 1, 'AP', cd.Fecha 
        FROM dbo.CxcDet cd JOIN dbo.Cxc nd ON cd.idCxcDebito = nd.idCxc
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'MORA DEL RECIBO %'
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WHERE cg.GUIDDocumento = cd.idCxcDet AND cg.DebCre = 1);

        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), cd.idCxcDet, '10105002', 2, cd.TotalAplicado, 'APLICACION MORA', 1, 'AP', cd.Fecha 
        FROM dbo.CxcDet cd JOIN dbo.Cxc nd ON cd.idCxcDebito = nd.idCxc
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'MORA DEL RECIBO %'
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WHERE cg.GUIDDocumento = cd.idCxcDet AND cg.DebCre = 2);

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END
GO

GO

-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- SCRIPT: 07_sp_HistorialPrestamosCliente.sql
-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- =========================================================================================
-- SP: cxcHistorialPrestamosCliente (Historial completo de préstamos y perfil de cliente)
-- Versión Robusta: Con Fallbacks directos a tb_clientes y Financiera.dbo.Cliente
-- =========================================================================================
USE Financiera
GO

IF OBJECT_ID('dbo.cxcHistorialPrestamosCliente', 'P') IS NOT NULL
    DROP PROCEDURE dbo.cxcHistorialPrestamosCliente
GO

CREATE PROCEDURE dbo.cxcHistorialPrestamosCliente
    @idCliente INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Hoy DATE = CAST(GETDATE() AS DATE);

    -- ─────────────────────────────────────────────────────────────────
    -- RS 1: Perfil y Datos del Cliente
    -- Prioridad:
    --   1. vw_datos_clientes (enriquecido con empresa, puesto, salario, referencias)
    --   2. tb_clientes (si no estaba en la vista por falta de contrato o catálogo)
    --   3. Financiera.dbo.Cliente (si está sincronizado en el ERP)
    -- ─────────────────────────────────────────────────────────────────
    IF EXISTS (SELECT 1 FROM dbsolonegocios.dbo.vw_datos_clientes WHERE CODIGO = @idCliente)
    BEGIN
        SELECT TOP 1
            vc.CODIGO                                              AS idCliente,
            vc.NOMBRE_COMPLETO                                     AS nombreCompleto,
            vc.IDENTIDAD                                           AS cedula,
            vc.CELULAR                                             AS telefono,
            vc.CORREO                                              AS correo,
            vc.DIRECCION                                           AS direccion,
            vc.OFICINA                                             AS oficina,
            CAST(ISNULL(tc.cl_fecha_reg, TRY_CAST(vc.FECHA_REGISTRO AS DATE)) AS DATE) AS fechaRegistro,
            vc.EMPRESA                                             AS empresa,
            vc.POSICION                                            AS cargoEmpresa,
            CAST(ISNULL(vc.SALARIO, 0) AS DECIMAL(18,2))           AS salario,
            CASE 
                WHEN op.ultimoOperador IS NOT NULL AND op.ultimoOperador <> '' AND op.ultimoOperador <> '0'
                    THEN op.ultimoOperador
                WHEN vc.OPERADOR IS NOT NULL AND vc.OPERADOR <> '' AND vc.OPERADOR <> '0' 
                    THEN vc.OPERADOR
                WHEN vc.GESTOR IS NOT NULL AND vc.GESTOR <> '' AND vc.GESTOR <> '0' 
                    THEN vc.GESTOR
                ELSE 'SADE'
            END                                                    AS creador,
            vc.SEXO                                                AS sexo,
            vc.PROBLEMATICO                                        AS esProblematico,
            vc.BANCO                                               AS banco,
            vc.CUENTA                                              AS cuentaBancaria,

            -- Referencias personales
            vc.NOMBRE_REFERENCIA_UNO                               AS nombreRef1,
            CAST(vc.TIPO_REFENRECIA_UNO AS VARCHAR(50))            AS parentescoRef1,
            vc.TEL_REFERENCIA_UNO                                  AS telRef1,
            vc.DIR_REFERENCIA_UNO                                  AS dirRef1,
            vc.NOMBRE_REFERENCIA_DOS                               AS nombreRef2,
            CAST(vc.TIPO_REFERENCIA_DOS AS VARCHAR(50))            AS parentescoRef2,
            vc.TEL_REFERENCIA_DOS                                  AS telRef2,
            vc.DIR_REFERENCIA_DOS                                  AS dirRef2,

            -- Estadísticas globales
            (SELECT COUNT(*) FROM dbsolonegocios.dbo.tb_prestamos WHERE pr_id_cliente = vc.CODIGO) AS totalPrestamos,
            (SELECT COUNT(*) FROM dbsolonegocios.dbo.tb_prestamos WHERE pr_id_cliente = vc.CODIGO AND pr_estado = 1 AND ISNULL(pr_balance, 0) > 0) AS prestamosActivos,
            CASE 
                WHEN (SELECT COUNT(*) FROM dbsolonegocios.dbo.tb_prestamos WHERE pr_id_cliente = vc.CODIGO) > 1 
                    THEN 'REENGANCHADO' 
                ELSE 'NUEVO' 
            END AS clasificacionGlobal
        FROM dbsolonegocios.dbo.vw_datos_clientes vc
        LEFT JOIN dbsolonegocios.dbo.tb_clientes tc ON tc.cl_id_cliente = vc.CODIGO
        OUTER APPLY (
            SELECT TOP 1 p.pr_operador AS ultimoOperador
            FROM dbsolonegocios.dbo.tb_prestamos p
            WHERE p.pr_id_cliente = vc.CODIGO
              AND p.pr_operador IS NOT NULL AND p.pr_operador <> '' AND p.pr_operador <> '0'
            ORDER BY p.pr_fecha DESC, p.pr_id_prestamos DESC
        ) op
        WHERE vc.CODIGO = @idCliente;
    END
    ELSE IF EXISTS (SELECT 1 FROM dbsolonegocios.dbo.tb_clientes WHERE cl_id_cliente = @idCliente)
    BEGIN
        SELECT
            c.cl_id_cliente                                        AS idCliente,
            ISNULL(RTRIM(LTRIM(c.cl_nombre + ' ' + ISNULL(c.cl_apellido, ''))), 'CLIENTE #' + CAST(c.cl_id_cliente AS VARCHAR(20))) AS nombreCompleto,
            c.cl_identidad                                         AS cedula,
            ISNULL(c.cl_celular, c.cl_telefono_resd)               AS telefono,
            c.cl_correo                                            AS correo,
            c.cl_direccion                                         AS direccion,
            CAST(c.cl_id_oficina AS VARCHAR(100))                  AS oficina,
            CAST(c.cl_fecha_reg AS DATE)                           AS fechaRegistro,
            ''                                                     AS empresa,
            ''                                                     AS cargoEmpresa,
            0.00                                                   AS salario,
            CASE 
                WHEN op.ultimoOperador IS NOT NULL AND op.ultimoOperador <> '' AND op.ultimoOperador <> '0'
                    THEN op.ultimoOperador
                WHEN c.cl_operador IS NOT NULL AND c.cl_operador <> '' AND c.cl_operador <> '0' 
                    THEN c.cl_operador
                ELSE 'SADE'
            END                                                    AS creador,
            c.cl_sexo                                              AS sexo,
            0                                                      AS esProblematico,
            ''                                                     AS banco,
            ''                                                     AS cuentaBancaria,

            rp.rp_nombre1                                          AS nombreRef1,
            CAST(rp.rp_tipo_referencia1 AS VARCHAR(50))            AS parentescoRef1,
            rp.rp_telefono1                                        AS telRef1,
            rp.rp_direccion1                                       AS dirRef1,
            rp.rp_nombre2                                          AS nombreRef2,
            CAST(rp.rp_tipo_referencia2 AS VARCHAR(50))            AS parentescoRef2,
            rp.rp_telefono2                                        AS telRef2,
            rp.rp_direccion2                                       AS dirRef2,

            (SELECT COUNT(*) FROM dbsolonegocios.dbo.tb_prestamos WHERE pr_id_cliente = c.cl_id_cliente) AS totalPrestamos,
            (SELECT COUNT(*) FROM dbsolonegocios.dbo.tb_prestamos WHERE pr_id_cliente = c.cl_id_cliente AND pr_estado = 1 AND ISNULL(pr_balance, 0) > 0) AS prestamosActivos,
            CASE 
                WHEN (SELECT COUNT(*) FROM dbsolonegocios.dbo.tb_prestamos WHERE pr_id_cliente = c.cl_id_cliente) > 1 
                    THEN 'REENGANCHADO' 
                ELSE 'NUEVO' 
            END AS clasificacionGlobal
        FROM dbsolonegocios.dbo.tb_clientes c
        LEFT JOIN dbsolonegocios.dbo.tb_referencia_personales rp 
            ON rp.rp_cod_cliente = c.cl_id_cliente AND rp.rp_id_oficina = c.cl_id_oficina
        OUTER APPLY (
            SELECT TOP 1 p.pr_operador AS ultimoOperador
            FROM dbsolonegocios.dbo.tb_prestamos p
            WHERE p.pr_id_cliente = c.cl_id_cliente
              AND p.pr_operador IS NOT NULL AND p.pr_operador <> '' AND p.pr_operador <> '0'
            ORDER BY p.pr_fecha DESC, p.pr_id_prestamos DESC
        ) op
        WHERE c.cl_id_cliente = @idCliente;
    END
    ELSE
    BEGIN
        -- Fallback a Financiera.dbo.Cliente
        SELECT
            cli.idCliente                                          AS idCliente,
            ISNULL(cli.Cliente, 'CLIENTE #' + CAST(cli.idCliente AS VARCHAR(20))) AS nombreCompleto,
            cli.RNC_Cedula                                         AS cedula,
            cli.Telefono                                           AS telefono,
            cli.EMail                                              AS correo,
            cli.Direccion                                          AS direccion,
            ''                                                     AS oficina,
            CAST(cli.FechaActivo AS DATE)                          AS fechaRegistro,
            ''                                                     AS empresa,
            ''                                                     AS cargoEmpresa,
            0.00                                                   AS salario,
            ISNULL(NULLIF(cli.UserName, ''), 'SADE')               AS creador,
            ''                                                     AS sexo,
            0                                                      AS esProblematico,
            ''                                                     AS banco,
            ''                                                     AS cuentaBancaria,

            CAST('' AS VARCHAR(200))                               AS nombreRef1,
            CAST('' AS VARCHAR(50))                                AS parentescoRef1,
            CAST('' AS VARCHAR(50))                                AS telRef1,
            CAST('' AS VARCHAR(300))                               AS dirRef1,
            CAST('' AS VARCHAR(200))                               AS nombreRef2,
            CAST('' AS VARCHAR(50))                                AS parentescoRef2,
            CAST('' AS VARCHAR(50))                                AS telRef2,
            CAST('' AS VARCHAR(300))                               AS dirRef2,

            ISNULL((SELECT COUNT(*) FROM Financiera.dbo.Cxc WHERE idCliente = cli.idCliente AND idTipoDocumento = 'FT'), 1) AS totalPrestamos,
            ISNULL((SELECT COUNT(*) FROM Financiera.dbo.Cxc WHERE idCliente = cli.idCliente AND idTipoDocumento = 'FT' AND Cancelado = 0), 0) AS prestamosActivos,
            CASE 
                WHEN (SELECT COUNT(*) FROM Financiera.dbo.Cxc WHERE idCliente = cli.idCliente AND idTipoDocumento = 'FT') > 1 
                    THEN 'REENGANCHADO' 
                ELSE 'NUEVO' 
            END AS clasificacionGlobal
        FROM Financiera.dbo.Cliente cli
        WHERE cli.idCliente = @idCliente;
    END

    -- ─────────────────────────────────────────────────────────────────
    -- RS 2: Historial de todos los préstamos del cliente
    -- ─────────────────────────────────────────────────────────────────
    IF EXISTS (SELECT 1 FROM dbsolonegocios.dbo.tb_prestamos WHERE pr_id_cliente = @idCliente)
    BEGIN
        SELECT 
            CAST(p.pr_id_prestamos AS VARCHAR(50))                 AS numeroPrestamo,
            CAST(p.pr_monto AS DECIMAL(18,2))                      AS montoOriginal,
            CAST(ISNULL(p.pr_interes, 0) AS DECIMAL(18,2))         AS interesOriginal,
            CAST(ISNULL(p.pr_monto, 0) + ISNULL(p.pr_interes, 0) AS DECIMAL(18,2)) AS totalOriginal,
            CAST(ISNULL(p.pr_tasa_interes, 0) AS FLOAT)            AS tasa,
            CAST(p.pr_fecha AS DATE)                               AS fechaPrestamo,
            CAST(p.pr_fecha_venc AS DATE)                          AS fechaVencimiento,
            p.pr_estado                                            AS idEstado,
            CASE 
                WHEN p.pr_estado = 1 AND ISNULL(p.pr_balance, 0) > 0 THEN 'ACTIVO' 
                ELSE 'SALDADO' 
            END                                                    AS estado,
            CAST(ISNULL(p.pr_balance, 0) AS DECIMAL(18,2))         AS balanceTotal,
            CAST(ISNULL(bal.balanceCapital, ISNULL(p.pr_balance, 0)) AS DECIMAL(18,2)) AS balanceCapital,
            CAST(ISNULL(pag.capitalPagado, 0) AS DECIMAL(18,2))    AS capitalPagado,
            CAST(ISNULL(pag.interesPagado, 0) AS DECIMAL(18,2))    AS interesPagado,
            CAST(ISNULL(pag.totalPagado, 0) AS DECIMAL(18,2))      AS totalPagado,
            CASE 
                WHEN p.pr_operador IS NOT NULL AND p.pr_operador <> '' AND p.pr_operador <> '0' 
                    THEN p.pr_operador 
                ELSE 'SADE' 
            END                                                    AS creador,
            uv.ultimoVencimiento,
            CASE 
                WHEN p.pr_balance <= 0 OR p.pr_estado <> 1 THEN 0.00
                WHEN DATEDIFF(day, ISNULL(uv.ultimoVencimiento, p.pr_fecha), @Hoy) <= 5
                    THEN ISNULL(bal.balanceCapital, ISNULL(p.pr_balance, 0))
                ELSE 
                    ROUND(ISNULL(bal.balanceCapital, ISNULL(p.pr_balance, 0)) * (1.0 + (ISNULL(p.pr_tasa_interes, 0) / 100.0)), 2)
            END                                                    AS montoSaldarHoy
        FROM dbsolonegocios.dbo.tb_prestamos p
        OUTER APPLY (
            SELECT SUM(dp.dp_saldo_capital) AS balanceCapital
            FROM dbsolonegocios.dbo.tb_detalle_prestamos dp
            WHERE dp.dp_id_prestamos = p.pr_id_prestamos
              AND dp.dp_id_oficina = p.pr_id_oficina
              AND dp.dp_estado = 1
        ) bal
        OUTER APPLY (
            SELECT MAX(dp2.dp_fecha_venc) AS ultimoVencimiento
            FROM dbsolonegocios.dbo.tb_detalle_prestamos dp2
            WHERE dp2.dp_id_prestamos = p.pr_id_prestamos 
              AND dp2.dp_id_oficina = p.pr_id_oficina
              AND dp2.dp_estado <> 0 
              AND CAST(dp2.dp_fecha_venc AS DATE) <= @Hoy
        ) uv
        OUTER APPLY (
            SELECT 
                SUM(rp.rp_capital)      AS capitalPagado,
                SUM(rp.rp_interes)      AS interesPagado,
                SUM(rp.rp_total_pagado) AS totalPagado
            FROM dbsolonegocios.dbo.tb_recibo_pagos rp
            WHERE rp.rp_id_prestamo = p.pr_id_prestamos
              AND rp.rp_id_oficina = p.pr_id_oficina
              AND rp.rp_estado = 1
              AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
        ) pag
        WHERE p.pr_id_cliente = @idCliente
        ORDER BY p.pr_fecha DESC, p.pr_id_prestamos DESC;
    END
    ELSE
    BEGIN
        -- Fallback a Financiera.dbo.Cxc
        SELECT 
            CAST(c.Cxc AS VARCHAR(50))                             AS numeroPrestamo,
            CAST(ISNULL(c.Valor, 0) AS DECIMAL(18,2))              AS montoOriginal,
            0.00                                                   AS interesOriginal,
            CAST(ISNULL(c.Valor, 0) AS DECIMAL(18,2))              AS totalOriginal,
            CAST(ISNULL(c.Tasa, 0) AS FLOAT)                       AS tasa,
            CAST(c.Fecha AS DATE)                                  AS fechaPrestamo,
            CAST(c.Vencimiento AS DATE)                            AS fechaVencimiento,
            CASE WHEN c.Cancelado = 0 THEN 1 ELSE 0 END            AS idEstado,
            CASE WHEN c.Cancelado = 0 THEN 'ACTIVO' ELSE 'SALDADO' END AS estado,
            CAST(ISNULL(c.Valor, 0) - ISNULL(pag.totalPagado, 0) AS DECIMAL(18,2)) AS balanceTotal,
            CAST(ISNULL(c.Valor, 0) - ISNULL(pag.totalPagado, 0) AS DECIMAL(18,2)) AS balanceCapital,
            CAST(ISNULL(pag.capitalPagado, 0) AS DECIMAL(18,2))    AS capitalPagado,
            CAST(ISNULL(pag.interesPagado, 0) AS DECIMAL(18,2))    AS interesPagado,
            CAST(ISNULL(pag.totalPagado, 0) AS DECIMAL(18,2))      AS totalPagado,
            ISNULL(NULLIF(c.Usuario, ''), 'SADE')                  AS creador,
            c.Vencimiento                                          AS ultimoVencimiento,
            CASE 
                WHEN c.Cancelado = 1 THEN 0.00
                ELSE CAST(ISNULL(c.Valor, 0) - ISNULL(pag.totalPagado, 0) AS DECIMAL(18,2))
            END                                                    AS montoSaldarHoy
        FROM Financiera.dbo.Cxc c
        OUTER APPLY (
            SELECT 
                SUM(CASE WHEN d.Referencia LIKE 'RP:%' OR d.Referencia NOT LIKE '%INTERES%' THEN d.Valor ELSE 0 END) AS capitalPagado,
                SUM(CASE WHEN d.Referencia LIKE '%INTERES%' THEN d.Valor ELSE 0 END) AS interesPagado,
                SUM(d.Valor) AS totalPagado
            FROM Financiera.dbo.CxcDet d
            WHERE d.idCxcDebito = c.idCxc
        ) pag
        WHERE c.idCliente = @idCliente AND c.idTipoDocumento = 'FT'
        ORDER BY c.Fecha DESC;
    END

END
GO

GO

-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- SCRIPT: 08_sp_ReporteDetalleClientes.sql
-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- =========================================================================================
-- SP: cxcReporteDetalleClientes (Informe 1: Detalle Individual de Clientes por Quincena)
-- =========================================================================================
-- Fórmulas Oficiales Implementadas:
--   1. Capital Actual Adeudado = Monto Préstamo Inicial - Capital Pagado
--   2. Balance Antes del Cobro = Monto Préstamo Inicial - Capital Pagado + Capital Cobrado en la Quincena
--   3. Deduplicación estricta de clientes por (id_oficina, id_cliente) y exclusión de Notas de Crédito
--      (N.CREDITO) y liquidaciones internas de reenganche para evitar cobros artificialmente inflados.
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
    @tipoReporte      VARCHAR(30)  = 'TODOS'  -- 'TODOS' | 'NUEVOS' | 'REENGANCHADOS' | 'EN MORA' | 'AL DIA'
AS
BEGIN
    SET NOCOUNT ON;

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

    -- El rango de evaluación de cobros quincenales respeta exactamente el período seleccionado
    DECLARE @InicioQuincena DATE = @fechaDesde;
    DECLARE @FinQuincena    DATE = @fechaHasta;
    DECLARE @Hoy            DATE = CAST(GETDATE() AS DATE);

    -- ── Tabla temporal de Préstamos Principales / Evaluados ──────────
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
        comentario              VARCHAR(250),
        totalPrestamosHist      INT,
        esNuevoEnPeriodo        BIT,
        esReengancheEnPeriodo   BIT
    );

    -- 1. Clientes únicos sin duplicación cartesiana de vistas
    ;WITH ClientesUnicos AS (
        SELECT
            c.cl_id_oficina AS idOficina,
            c.cl_id_cliente AS idCliente,
            ISNULL(
                NULLIF(LTRIM(RTRIM(vc.NOMBRE_COMPLETO)), ''),
                ISNULL(NULLIF(LTRIM(RTRIM(ISNULL(c.cl_nombre, '') + ' ' + ISNULL(c.cl_apellido, ''))), ''), 'CLIENTE #' + CAST(c.cl_id_cliente AS VARCHAR(20)))
            ) AS nombreCliente,
            ISNULL(vc.IDENTIDAD, c.cl_identidad) AS cedula,
            ISNULL(
                NULLIF(LTRIM(RTRIM(vc.EMPRESA)), ''),
                ISNULL(NULLIF(LTRIM(RTRIM(co.co_nombre)), ''), 'Sin Cartera')
            ) AS empresa
        FROM (
            SELECT *,
                ROW_NUMBER() OVER (PARTITION BY cl_id_oficina, cl_id_cliente ORDER BY cl_fecha_reg DESC) AS rn_cli
            FROM dbsolonegocios.dbo.tb_clientes
        ) c
        OUTER APPLY (
            SELECT TOP 1 vc1.NOMBRE_COMPLETO, vc1.IDENTIDAD, vc1.EMPRESA
            FROM dbsolonegocios.dbo.vw_datos_clientes vc1
            WHERE vc1.CODIGO = c.cl_id_cliente AND vc1.ID_OFICINA = c.cl_id_oficina
        ) vc
        OUTER APPLY (
            SELECT TOP 1 cp.co_nombre
            FROM dbsolonegocios.dbo.tb_datos_laboral dl
            INNER JOIN dbsolonegocios.dbo.tb_compania cp ON cp.co_id = dl.dl_id_empresa
            WHERE dl.dl_id_cliente = c.cl_id_cliente AND dl.dl_id_oficina = c.cl_id_oficina
            ORDER BY dl.dl_id DESC
        ) co
        WHERE c.rn_cli = 1
    ),
    -- 2. Pagos históricos reales acumulados de capital por préstamo (excluyendo N.CREDITO y cierres admin)
    PagosHistoricos AS (
        SELECT 
            rp.rp_id_oficina,
            rp.rp_id_prestamo,
            ISNULL(SUM(rp.rp_capital), 0) AS capitalPagadoTotal
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
    -- 3. Cobros efectivos reales de la quincena por préstamo
    CobrosQuincena AS (
        SELECT 
            rp.rp_id_oficina,
            rp.rp_id_prestamo,
            ISNULL(SUM(rp.rp_capital), 0)      AS capitalCobrado,
            ISNULL(SUM(rp.rp_interes), 0)      AS interesCobrado,
            ISNULL(SUM(rp.rp_capital + rp.rp_interes + ISNULL(rp.rp_mora, 0)), 0) AS totalCobrado
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp
        WHERE rp.rp_estado = 1
          AND CAST(rp.rp_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena
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
    -- 4. Cobros efectivos reales de la quincena por cliente (por si abonó al préstamo anterior antes de reenganchar en la misma quincena)
    CobrosQuincenaCliente AS (
        SELECT
            p.pr_id_oficina,
            p.pr_id_cliente,
            ISNULL(SUM(cq.capitalCobrado), 0) AS capitalCobradoCliente,
            ISNULL(SUM(cq.interesCobrado), 0) AS interesCobradoCliente,
            ISNULL(SUM(cq.totalCobrado), 0)   AS totalCobradoCliente
        FROM CobrosQuincena cq
        INNER JOIN dbsolonegocios.dbo.tb_prestamos p
            ON p.pr_id_prestamos = cq.rp_id_prestamo AND p.pr_id_oficina = cq.rp_id_oficina
        WHERE ISNULL(p.pr_estado, 0) <> 0
        GROUP BY p.pr_id_oficina, p.pr_id_cliente
    ),
    -- 5. Estado de cuotas pendientes reales (dp_estado = 1)
    CuotasInfo AS (
        SELECT 
            dp.dp_id_oficina,
            dp.dp_id_prestamos,
            ISNULL(SUM(dp.dp_saldo_capital), 0) AS balanceCapital,
            ISNULL(SUM(dp.dp_saldo_capital + dp.dp_saldo_interes), 0) AS balanceTotalCuotas,
            SUM(CASE WHEN dp.dp_estado = 1 AND CAST(dp.dp_fecha_venc AS DATE) < @Hoy AND (ISNULL(dp.dp_saldo_capital, 0) + ISNULL(dp.dp_saldo_interes, 0)) > 0 THEN 1 ELSE 0 END) AS cuotasVencidas
        FROM dbsolonegocios.dbo.tb_detalle_prestamos dp
        WHERE dp.dp_estado = 1
        GROUP BY dp.dp_id_oficina, dp.dp_id_prestamos
    ),
    -- 6. Préstamo principal o representativo por cliente en la quincena
    PrestamosCliente AS (
        SELECT 
            p.pr_id_oficina,
            p.pr_id_cliente,
            p.pr_id_prestamos,
            ISNULL(p.pr_monto, 0) AS pr_monto,
            ISNULL(p.pr_tasa_interes, 0) AS pr_tasa_interes,
            p.pr_fecha,
            p.pr_fecha_venc,
            p.pr_balance,
            p.pr_estado,
            ISNULL(ph.capitalPagadoTotal, 0) AS capitalPagadoTotal,
            CASE 
                WHEN p.pr_estado = 1 
                     AND (ISNULL(p.pr_monto, 0) - ISNULL(ph.capitalPagadoTotal, 0)) > 0
                     AND NOT EXISTS (
                         SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg
                         WHERE rg.rg_id_prestamo = p.pr_id_prestamos AND rg.rg_id_oficina = p.pr_id_oficina
                     )
                THEN 1 ELSE 0 
            END AS esActivo,
            ROW_NUMBER() OVER (
                PARTITION BY p.pr_id_oficina, p.pr_id_cliente 
                ORDER BY 
                    -- Priorizar préstamos otorgados en el período o con cobro en la quincena
                    CASE WHEN CAST(p.pr_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena THEN 0 ELSE 1 END,
                    CASE WHEN ISNULL(cq.totalCobrado, 0) > 0 THEN 0 ELSE 1 END,
                    CASE 
                        WHEN p.pr_estado = 1 
                             AND (ISNULL(p.pr_monto, 0) - ISNULL(ph.capitalPagadoTotal, 0)) > 0
                             AND NOT EXISTS (
                                 SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg
                                 WHERE rg.rg_id_prestamo = p.pr_id_prestamos AND rg.rg_id_oficina = p.pr_id_oficina
                             )
                        THEN 0 ELSE 1 
                    END,
                    p.pr_fecha DESC, 
                    p.pr_id_prestamos DESC
            ) AS rn
        FROM dbsolonegocios.dbo.tb_prestamos p
        LEFT JOIN PagosHistoricos ph
            ON ph.rp_id_prestamo = p.pr_id_prestamos AND ph.rp_id_oficina = p.pr_id_oficina
        LEFT JOIN CobrosQuincena cq
            ON cq.rp_id_prestamo = p.pr_id_prestamos AND cq.rp_id_oficina = p.pr_id_oficina
        WHERE ISNULL(p.pr_estado, 0) <> 0
    ),
    PrestamoPrincipal AS (
        SELECT * FROM PrestamosCliente WHERE rn = 1
    ),
    HistorialCliente AS (
        SELECT 
            p.pr_id_oficina,
            p.pr_id_cliente,
            COUNT(*) AS totalPrestamos,
            MIN(p.pr_fecha) AS primerPrestamo,
            MAX(p.pr_fecha) AS ultimoPrestamo
        FROM dbsolonegocios.dbo.tb_prestamos p
        WHERE ISNULL(p.pr_estado, 0) <> 0
        GROUP BY p.pr_id_oficina, p.pr_id_cliente
    )
    INSERT INTO #ReporteDetalle
    SELECT 
        cu.idOficina,
        cu.idCliente,
        cu.nombreCliente,
        cu.cedula,
        cu.empresa,
        CAST(pa.pr_id_prestamos AS VARCHAR(50))                          AS numeroPrestamo,
        CAST(pa.pr_monto AS DECIMAL(18,2))                               AS montoPrestamo,

        -- Capital Pagado (acumulado histórico real del préstamo, topeado al monto del préstamo)
        CAST(
            CASE 
                WHEN pa.capitalPagadoTotal > pa.pr_monto THEN pa.pr_monto
                WHEN pa.capitalPagadoTotal < 0 THEN 0.00
                ELSE pa.capitalPagadoTotal
            END AS DECIMAL(18,2)
        ) AS capitalPagado,

        -- Balance Antes del Cobro = Monto Préstamo Inicial - Capital Pagado + Capital Cobrado en la Quincena
        CAST(
            (CASE 
                WHEN (pa.pr_monto - pa.capitalPagadoTotal) < 0 THEN 0.00 
                ELSE (pa.pr_monto - pa.capitalPagadoTotal) 
            END)
            + ISNULL(NULLIF(cq.capitalCobrado, 0), ISNULL(cqc.capitalCobradoCliente, 0))
            AS DECIMAL(18,2)
        ) AS balanceAntesCobro,

        CAST(pa.pr_tasa_interes AS FLOAT)                                AS tasa,
        pa.pr_fecha                                                      AS fechaPrestamo,
        CAST(ISNULL(NULLIF(cq.capitalCobrado, 0), ISNULL(cqc.capitalCobradoCliente, 0)) AS DECIMAL(18,2)) AS capitalCobradoQuincena,
        CAST(ISNULL(NULLIF(cq.interesCobrado, 0), ISNULL(cqc.interesCobradoCliente, 0)) AS DECIMAL(18,2)) AS interesCobradoQuincena,

        -- Capital Actual Adeudado = Capital Préstamo Inicial - Capital Pagado
        CAST(
            CASE 
                WHEN (pa.pr_monto - pa.capitalPagadoTotal) < 0 THEN 0.00 
                ELSE (pa.pr_monto - pa.capitalPagadoTotal) 
            END AS DECIMAL(18,2)
        ) AS capitalActualAdeudado,

        CAST(ISNULL(NULLIF(cq.totalCobrado, 0), ISNULL(cqc.totalCobradoCliente, 0)) AS DECIMAL(18,2)) AS totalCobradoQuincena,
        
        -- Balance actual adeudado (consistente con Capital Actual Adeudado)
        CAST(
            CASE 
                WHEN (pa.pr_monto - pa.capitalPagadoTotal) < 0 THEN 0.00 
                ELSE (pa.pr_monto - pa.capitalPagadoTotal) 
            END AS DECIMAL(18,2)
        ) AS balanceActual,

        -- Clasificación exacta:
        CASE 
            WHEN CAST(pa.pr_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena AND ISNULL(hc.totalPrestamos, 1) <= 1
                THEN 'NUEVO'
            WHEN CAST(pa.pr_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena AND ISNULL(hc.totalPrestamos, 1) > 1
                THEN 'REENGANCHADO'
            WHEN ISNULL(ci.cuotasVencidas, 0) > 0 AND pa.esActivo = 1
                THEN 'SITUACION ATRASO'
            WHEN pa.esActivo = 0
                THEN 'CANCELADO'
            ELSE 'AL DIA'
        END AS clasificacion,

        -- Comentario automático
        CASE 
            WHEN CAST(pa.pr_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena AND ISNULL(hc.totalPrestamos, 1) <= 1
                THEN 'Préstamo nuevo otorgado en período'
            WHEN CAST(pa.pr_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena AND ISNULL(hc.totalPrestamos, 1) > 1
                THEN 'Reenganche otorgado en período'
            WHEN ISNULL(ci.cuotasVencidas, 0) > 0 AND pa.esActivo = 1
                THEN 'Presenta cuotas con atraso'
            WHEN ISNULL(NULLIF(cq.totalCobrado, 0), ISNULL(cqc.totalCobradoCliente, 0)) > 0
                THEN 'Cobro quincenal aplicado'
            ELSE ''
        END AS comentario,

        ISNULL(hc.totalPrestamos, 1) AS totalPrestamosHist,
        CASE WHEN CAST(pa.pr_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena AND ISNULL(hc.totalPrestamos, 1) <= 1 THEN 1 ELSE 0 END AS esNuevoEnPeriodo,
        CASE WHEN CAST(pa.pr_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena AND ISNULL(hc.totalPrestamos, 1) > 1 THEN 1 ELSE 0 END AS esReengancheEnPeriodo

    FROM ClientesUnicos cu
    INNER JOIN PrestamoPrincipal pa
        ON pa.pr_id_cliente = cu.idCliente AND pa.pr_id_oficina = cu.idOficina
    LEFT JOIN HistorialCliente hc
        ON hc.pr_id_cliente = cu.idCliente AND hc.pr_id_oficina = cu.idOficina
    LEFT JOIN CobrosQuincena cq
        ON cq.rp_id_prestamo = pa.pr_id_prestamos AND cq.rp_id_oficina = pa.pr_id_oficina
    LEFT JOIN CobrosQuincenaCliente cqc
        ON cqc.pr_id_cliente = cu.idCliente AND cqc.pr_id_oficina = cu.idOficina
    LEFT JOIN CuotasInfo ci
        ON ci.dp_id_prestamos = pa.pr_id_prestamos AND ci.dp_id_oficina = pa.pr_id_oficina
    WHERE 
        (@empresa IS NULL OR cu.empresa LIKE '%' + @empresa + '%')
        -- Solo incluir clientes que tengan actividad (préstamo activo, cobro en la quincena o préstamo en el período)
        AND (
            pa.esActivo = 1 
            OR ISNULL(cq.totalCobrado, 0) > 0
            OR ISNULL(cqc.totalCobradoCliente, 0) > 0
            OR CAST(pa.pr_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena
        );

    -- Filtrar por Tipo de Reporte si se especifica
    SET @tipoReporte = UPPER(ISNULL(NULLIF(RTRIM(LTRIM(@tipoReporte)), ''), 'TODOS'));

    IF @tipoReporte = 'NUEVOS'
        DELETE FROM #ReporteDetalle WHERE clasificacion <> 'NUEVO';
    ELSE IF @tipoReporte = 'REENGANCHADOS'
        DELETE FROM #ReporteDetalle WHERE clasificacion <> 'REENGANCHADO';
    ELSE IF @tipoReporte = 'EN MORA' OR @tipoReporte = 'ATRASO'
        DELETE FROM #ReporteDetalle WHERE clasificacion <> 'SITUACION ATRASO';
    ELSE IF @tipoReporte = 'AL DIA'
        DELETE FROM #ReporteDetalle WHERE clasificacion <> 'AL DIA';

    -- ── Result Set 1: Listado Detalle ────────────────────────────────
    SELECT 
        idCliente,
        clasificacion,
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
    ORDER BY empresa, nombreCliente;

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

    DROP TABLE #ReporteDetalle;
END
GO

GO

-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- SCRIPT: 09_sp_ReporteConsolidadoCartera.sql
-- >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
-- =========================================================================================
-- SP: cxcReporteConsolidadoCartera (Informe 2: Resumen Consolidado por Cartera Quincenal)
-- =========================================================================================
-- Correcciones de Conciliación Estricta con cxcReporteDetalleClientes:
--   1. Reporte Quincenal: Acepta @fechaCorte, @empresa, @fechaDesde y @fechaHasta.
--      Hala los cobros reales de la quincena seleccionada (@InicioQuincena a @FinQuincena)
--      exactamente igual que el Detalle de Clientes.
--   2. Elimina la multiplicación cartesiana producida por vw_datos_clientes (deduplicando
--      por oficina + cliente) y evita sumar todos los préstamos históricos reenganchados
--      (evaluando el préstamo principal vigente por cliente).
--   3. Excluye Notas de Crédito (N.CREDITO) y cierres administrativos sin interés.
--   4. Capital Activo = Monto Préstamo Inicial - Capital Pagado + Capital Cobrado Quincena
--      (cuadra 100% peso a peso con el Balance Antes del Cobro del Detalle de Clientes).
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

    -- Tabla temporal con la evaluación única por cliente (idéntica a cxcReporteDetalleClientes)
    CREATE TABLE #ClientesCartera (
        idOficina               INT,
        idCliente               INT,
        cartera                 VARCHAR(200),
        montoPrestamo           DECIMAL(18,2),
        capitalPagado           DECIMAL(18,2),
        capitalActualAdeudado   DECIMAL(18,2),
        balanceAntesCobro       DECIMAL(18,2),
        capitalCobradoQuincena  DECIMAL(18,2),
        interesCobradoQuincena  DECIMAL(18,2),
        tasa                    FLOAT,
        esActivoEnQuincena      BIT
    );

    -- 1. Clientes únicos sin duplicación cartesiana
    ;WITH ClientesUnicos AS (
        SELECT
            c.cl_id_oficina AS idOficina,
            c.cl_id_cliente AS idCliente,
            ISNULL(
                NULLIF(LTRIM(RTRIM(vc.EMPRESA)), ''),
                ISNULL(NULLIF(LTRIM(RTRIM(co.co_nombre)), ''), 'Sin Cartera')
            ) AS cartera
        FROM (
            SELECT *,
                ROW_NUMBER() OVER (PARTITION BY cl_id_oficina, cl_id_cliente ORDER BY cl_fecha_reg DESC) AS rn_cli
            FROM dbsolonegocios.dbo.tb_clientes
        ) c
        OUTER APPLY (
            SELECT TOP 1 vc1.EMPRESA
            FROM dbsolonegocios.dbo.vw_datos_clientes vc1
            WHERE vc1.CODIGO = c.cl_id_cliente AND vc1.ID_OFICINA = c.cl_id_oficina
        ) vc
        OUTER APPLY (
            SELECT TOP 1 cp.co_nombre
            FROM dbsolonegocios.dbo.tb_datos_laboral dl
            INNER JOIN dbsolonegocios.dbo.tb_compania cp ON cp.co_id = dl.dl_id_empresa
            WHERE dl.dl_id_cliente = c.cl_id_cliente AND dl.dl_id_oficina = c.cl_id_oficina
            ORDER BY dl.dl_id DESC
        ) co
        WHERE c.rn_cli = 1
    ),
    -- 2. Pagos históricos reales acumulados de capital por préstamo (excluyendo N.CREDITO)
    PagosHistoricos AS (
        SELECT 
            rp.rp_id_oficina,
            rp.rp_id_prestamo,
            ISNULL(SUM(rp.rp_capital), 0) AS capitalPagadoTotal
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
    -- 3. Cobros efectivos reales de la quincena por préstamo
    CobrosQuincena AS (
        SELECT 
            rp.rp_id_oficina,
            rp.rp_id_prestamo,
            ISNULL(SUM(rp.rp_capital), 0)      AS capitalCobrado,
            ISNULL(SUM(rp.rp_interes), 0)      AS interesCobrado,
            ISNULL(SUM(rp.rp_capital + rp.rp_interes + ISNULL(rp.rp_mora, 0)), 0) AS totalCobrado
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp
        WHERE rp.rp_estado = 1
          AND CAST(rp.rp_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena
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
    -- 4. Cobros efectivos reales de la quincena por cliente
    CobrosQuincenaCliente AS (
        SELECT
            p.pr_id_oficina,
            p.pr_id_cliente,
            ISNULL(SUM(cq.capitalCobrado), 0) AS capitalCobradoCliente,
            ISNULL(SUM(cq.interesCobrado), 0) AS interesCobradoCliente,
            ISNULL(SUM(cq.totalCobrado), 0)   AS totalCobradoCliente
        FROM CobrosQuincena cq
        INNER JOIN dbsolonegocios.dbo.tb_prestamos p
            ON p.pr_id_prestamos = cq.rp_id_prestamo AND p.pr_id_oficina = cq.rp_id_oficina
        WHERE ISNULL(p.pr_estado, 0) <> 0
        GROUP BY p.pr_id_oficina, p.pr_id_cliente
    ),
    -- 5. Préstamo principal por cliente (misma lógica exacta que cxcReporteDetalleClientes)
    PrestamosCliente AS (
        SELECT 
            p.pr_id_oficina,
            p.pr_id_cliente,
            p.pr_id_prestamos,
            ISNULL(p.pr_monto, 0) AS pr_monto,
            ISNULL(p.pr_tasa_interes, 0) AS pr_tasa_interes,
            p.pr_fecha,
            p.pr_estado,
            ISNULL(ph.capitalPagadoTotal, 0) AS capitalPagadoTotal,
            CASE 
                WHEN p.pr_estado = 1 
                     AND (ISNULL(p.pr_monto, 0) - ISNULL(ph.capitalPagadoTotal, 0)) > 0
                     AND NOT EXISTS (
                         SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg
                         WHERE rg.rg_id_prestamo = p.pr_id_prestamos AND rg.rg_id_oficina = p.pr_id_oficina
                     )
                THEN 1 ELSE 0 
            END AS esActivo,
            ROW_NUMBER() OVER (
                PARTITION BY p.pr_id_oficina, p.pr_id_cliente 
                ORDER BY 
                    CASE WHEN CAST(p.pr_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena THEN 0 ELSE 1 END,
                    CASE WHEN ISNULL(cq.totalCobrado, 0) > 0 THEN 0 ELSE 1 END,
                    CASE 
                        WHEN p.pr_estado = 1 
                             AND (ISNULL(p.pr_monto, 0) - ISNULL(ph.capitalPagadoTotal, 0)) > 0
                             AND NOT EXISTS (
                                 SELECT 1 FROM dbsolonegocios.dbo.tb_reenganche rg
                                 WHERE rg.rg_id_prestamo = p.pr_id_prestamos AND rg.rg_id_oficina = p.pr_id_oficina
                             )
                        THEN 0 ELSE 1 
                    END,
                    p.pr_fecha DESC, 
                    p.pr_id_prestamos DESC
            ) AS rn
        FROM dbsolonegocios.dbo.tb_prestamos p
        LEFT JOIN PagosHistoricos ph
            ON ph.rp_id_prestamo = p.pr_id_prestamos AND ph.rp_id_oficina = p.pr_id_oficina
        LEFT JOIN CobrosQuincena cq
            ON cq.rp_id_prestamo = p.pr_id_prestamos AND cq.rp_id_oficina = p.pr_id_oficina
        WHERE ISNULL(p.pr_estado, 0) <> 0
    ),
    PrestamoPrincipal AS (
        SELECT * FROM PrestamosCliente WHERE rn = 1
    )
    INSERT INTO #ClientesCartera
    SELECT
        cu.idOficina,
        cu.idCliente,
        cu.cartera,
        CAST(pa.pr_monto AS DECIMAL(18,2)) AS montoPrestamo,
        CAST(
            CASE 
                WHEN pa.capitalPagadoTotal > pa.pr_monto THEN pa.pr_monto
                WHEN pa.capitalPagadoTotal < 0 THEN 0.00
                ELSE pa.capitalPagadoTotal
            END AS DECIMAL(18,2)
        ) AS capitalPagado,
        CAST(
            CASE 
                WHEN (pa.pr_monto - pa.capitalPagadoTotal) < 0 THEN 0.00
                ELSE (pa.pr_monto - pa.capitalPagadoTotal)
            END AS DECIMAL(18,2)
        ) AS capitalActualAdeudado,
        CAST(
            (CASE 
                WHEN (pa.pr_monto - pa.capitalPagadoTotal) < 0 THEN 0.00
                ELSE (pa.pr_monto - pa.capitalPagadoTotal)
            END)
            + ISNULL(NULLIF(cq.capitalCobrado, 0), ISNULL(cqc.capitalCobradoCliente, 0))
            AS DECIMAL(18,2)
        ) AS balanceAntesCobro,
        CAST(ISNULL(NULLIF(cq.capitalCobrado, 0), ISNULL(cqc.capitalCobradoCliente, 0)) AS DECIMAL(18,2)) AS capitalCobradoQuincena,
        CAST(ISNULL(NULLIF(cq.interesCobrado, 0), ISNULL(cqc.interesCobradoCliente, 0)) AS DECIMAL(18,2)) AS interesCobradoQuincena,
        CAST(pa.pr_tasa_interes AS FLOAT) AS tasa,
        CASE 
            WHEN pa.esActivo = 1 
                 OR ISNULL(cq.totalCobrado, 0) > 0
                 OR ISNULL(cqc.totalCobradoCliente, 0) > 0
                 OR CAST(pa.pr_fecha AS DATE) BETWEEN @InicioQuincena AND @FinQuincena
            THEN 1 ELSE 0
        END AS esActivoEnQuincena
    FROM ClientesUnicos cu
    INNER JOIN PrestamoPrincipal pa
        ON pa.pr_id_cliente = cu.idCliente AND pa.pr_id_oficina = cu.idOficina
    LEFT JOIN CobrosQuincena cq
        ON cq.rp_id_prestamo = pa.pr_id_prestamos AND cq.rp_id_oficina = pa.pr_id_oficina
    LEFT JOIN CobrosQuincenaCliente cqc
        ON cqc.pr_id_cliente = cu.idCliente AND cqc.pr_id_oficina = cu.idOficina
    WHERE (@empresa IS NULL OR cu.cartera LIKE '%' + @empresa + '%');

    -- ── Result Set 1: Resumen Consolidado por Cartera ────────────────
    ;WITH ResumenCartera AS (
        SELECT
            cc.cartera,
            -- Balance de Capital Colocado (Monto préstamo inicial de la cartera activa en la quincena)
            ISNULL(SUM(CASE WHEN cc.esActivoEnQuincena = 1 THEN cc.montoPrestamo ELSE 0 END), 0) AS balanceCapitalColocado,
            -- Capital de Clientes Inactivos / Cancelados
            ISNULL(SUM(CASE WHEN cc.esActivoEnQuincena = 0 THEN cc.montoPrestamo ELSE 0 END), 0) AS capitalClientesInactivosCancelados,
            -- Capital Activo (Balance Antes del Cobro = Monto Inicial - Capital Pagado + Capital Cobrado Quincena)
            ISNULL(SUM(CASE WHEN cc.esActivoEnQuincena = 1 THEN cc.balanceAntesCobro ELSE 0 END), 0) AS capitalActivo,
            -- Clientes Activos
            ISNULL(SUM(CASE WHEN cc.esActivoEnQuincena = 1 THEN 1 ELSE 0 END), 0) AS clientesActivos,
            -- Clientes Inactivos
            ISNULL(SUM(CASE WHEN cc.esActivoEnQuincena = 0 THEN 1 ELSE 0 END), 0) AS clientesInactivos,
            -- Cobros efectivos de la quincena seleccionada
            ISNULL(SUM(cc.capitalCobradoQuincena), 0) AS capitalCobradoQuincena,
            ISNULL(SUM(cc.interesCobradoQuincena), 0) AS interesCobradoQuincena,
            -- Tasa promedio de la cartera activa
            CASE
                WHEN SUM(CASE WHEN cc.esActivoEnQuincena = 1 THEN cc.montoPrestamo ELSE 0 END) > 0
                THEN ROUND(
                    SUM(CASE WHEN cc.esActivoEnQuincena = 1 THEN cc.montoPrestamo * cc.tasa ELSE 0 END)
                    / SUM(CASE WHEN cc.esActivoEnQuincena = 1 THEN cc.montoPrestamo ELSE 0 END),
                    2
                )
                WHEN AVG(cc.tasa) IS NOT NULL THEN ROUND(AVG(cc.tasa), 2)
                ELSE 0.00
            END AS tasa
        FROM #ClientesCartera cc
        GROUP BY cc.cartera
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
        COUNT(DISTINCT CASE WHEN esActivoEnQuincena = 1 OR capitalCobradoQuincena > 0 OR interesCobradoQuincena > 0 OR @empresa IS NOT NULL THEN cartera END) AS totalCarteras,
        ISNULL(SUM(CASE WHEN esActivoEnQuincena = 1 THEN montoPrestamo ELSE 0 END), 0)          AS totalBalanceCapitalColocado,
        ISNULL(SUM(CASE WHEN esActivoEnQuincena = 0 THEN montoPrestamo ELSE 0 END), 0)          AS totalCapitalInactivosCancelados,
        ISNULL(SUM(CASE WHEN esActivoEnQuincena = 1 THEN balanceAntesCobro ELSE 0 END), 0)      AS totalCapitalActivo,
        ISNULL(SUM(CASE WHEN esActivoEnQuincena = 1 THEN 1 ELSE 0 END), 0)                      AS totalClientesActivos,
        ISNULL(SUM(CASE WHEN esActivoEnQuincena = 0 THEN 1 ELSE 0 END), 0)                      AS totalClientesInactivos,
        ISNULL(SUM(capitalCobradoQuincena), 0)                                                  AS totalCapitalCobradoQuincena,
        ISNULL(SUM(interesCobradoQuincena), 0)                                                  AS totalInteresCobradoQuincena,
        CASE 
            WHEN SUM(CASE WHEN esActivoEnQuincena = 1 THEN montoPrestamo ELSE 0 END) > 0 
            THEN ROUND(
                SUM(CASE WHEN esActivoEnQuincena = 1 THEN montoPrestamo * tasa ELSE 0 END) 
                / SUM(CASE WHEN esActivoEnQuincena = 1 THEN montoPrestamo ELSE 0 END), 
                2
            )
            ELSE 0.00 
        END AS tasaPromedioPonderada,
        @fechaCorte                                                                             AS fechaCorte,
        @InicioQuincena                                                                         AS quincenaDesde,
        @FinQuincena                                                                            AS quincenaHasta
    FROM #ClientesCartera
    WHERE cartera IN (
        SELECT cartera
        FROM #ClientesCartera
        GROUP BY cartera
        HAVING SUM(CASE WHEN esActivoEnQuincena = 1 THEN 1 ELSE 0 END) > 0
            OR SUM(capitalCobradoQuincena) > 0
            OR SUM(interesCobradoQuincena) > 0
            OR @empresa IS NOT NULL
    );

    DROP TABLE #ClientesCartera;
END
GO

GO

