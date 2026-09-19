-- ============================================================
-- SP: cxcDashboardKPIs  (v2 - columnas reales de la BD)
-- ============================================================
-- Estructura real confirmada:
--   Cxc.idCxc          = UNIQUEIDENTIFIER (PK)
--   Cxc.Cxc            = VARCHAR (numero visible, ej. '17481')
--   Cxc.Valor          = monto original
--   Cxc.Cancelado      = BIT (equivale a anulado)
--   Cxc.Referencia     = UNIQUEIDENTIFIER (idCxc del padre)
--   Cxc.Vencimiento    = DATETIME
--   CxcDet.idCxc       = UNIQUEIDENTIFIER (RC que hizo el pago)
--   CxcDet.idCxcDebito = UNIQUEIDENTIFIER (documento saldado)
--   CxcDet.Valor       = monto aplicado
--   CxcDet.Referencia  = texto descriptor ('APL. INTERES...' / 'RP:...')
-- ============================================================
USE Financiera
GO

IF OBJECT_ID('dbo.cxcDashboardKPIs', 'P') IS NOT NULL
    DROP PROCEDURE dbo.cxcDashboardKPIs
GO

CREATE PROCEDURE dbo.cxcDashboardKPIs
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Hoy          DATE = CAST(GETDATE() AS DATE);
    DECLARE @InicioMes    DATE = DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1);
    DECLARE @FinMes       DATE = EOMONTH(GETDATE());

    -- ----------------------------------------------------------------
    -- 1. CARTERA ACTIVA: Préstamos (FT) con Cancelado=0
    --    Balance = Valor original - suma de pagos de capital en CxcDet
    -- ----------------------------------------------------------------
    ;WITH PagosCapital AS (
        -- Capital pagado a cada FT (CxcDet donde idCxcDebito = FT.idCxc
        -- y la Referencia NO contiene 'INTERES' para descontar solo capital)
        SELECT
            d.idCxcDebito,
            SUM(d.Valor) AS totalPagadoCapital
        FROM dbo.CxcDet d
        INNER JOIN dbo.Cxc rc ON rc.idCxc = d.idCxc
        WHERE rc.idTipoDocumento = 'RC'
          AND rc.Cancelado = 0
          -- La Referencia 'RP:NNNNN|P:NNNNN|C:N' identifica pago de capital
          AND (d.Referencia LIKE 'RP:%' OR d.Referencia NOT LIKE '%INTERES%')
          AND d.Referencia NOT LIKE 'APL. INTERES%'
        GROUP BY d.idCxcDebito
    ),
    CarteraActiva AS (
        SELECT
            COUNT(DISTINCT ft.idCxc)            AS totalPrestamos,
            SUM(ft.Valor)                       AS capitalOriginal,
            SUM(ft.Valor - ISNULL(pc.totalPagadoCapital, 0)) AS capitalPendiente
        FROM dbo.Cxc ft
        LEFT JOIN PagosCapital pc ON pc.idCxcDebito = ft.idCxc
        WHERE ft.idTipoDocumento = 'FT'
          AND ft.Cancelado = 0
          AND ft.esCxc = 1
    ),
    -- ----------------------------------------------------------------
    -- 2. COBROS DEL MES: Recibos (RC) del mes actual
    -- ----------------------------------------------------------------
    CobrosDelMes AS (
        SELECT
            -- Capital cobrado = CxcDet aplicado a FT directamente
            SUM(CASE WHEN d.Referencia LIKE 'RP:%' OR d.Referencia NOT LIKE 'APL. INTERES%'
                     THEN d.Valor ELSE 0 END) AS capitalCobrado,
            -- Interés cobrado = CxcDet aplicado a ND tipo 12
            SUM(CASE WHEN d.Referencia LIKE 'APL. INTERES%'
                     THEN d.Valor ELSE 0 END) AS interesCobrado,
            0.00                               AS moraCobrada,
            SUM(rc.Valor)                      AS totalCobrado,
            COUNT(DISTINCT rc.idCxc)           AS cantidadRecibos
        FROM dbo.Cxc rc
        INNER JOIN dbo.CxcDet d ON d.idCxc = rc.idCxc
        WHERE rc.idTipoDocumento = 'RC'
          AND rc.Cancelado = 0
          AND CAST(rc.Fecha AS DATE) BETWEEN @InicioMes AND @FinMes
    ),
    -- ----------------------------------------------------------------
    -- 3. PRÉSTAMOS ATRASADOS: FT cuyo Vencimiento ya pasó
    --    y todavía tienen balance > 0
    -- ----------------------------------------------------------------
    PrestamosAtrasados AS (
        SELECT COUNT(DISTINCT ft.idCxc) AS prestamosAtrasados
        FROM dbo.Cxc ft
        LEFT JOIN PagosCapital pc ON pc.idCxcDebito = ft.idCxc
        WHERE ft.idTipoDocumento = 'FT'
          AND ft.Cancelado = 0
          AND ft.esCxc = 1
          AND (ft.Valor - ISNULL(pc.totalPagadoCapital, 0)) > 0
          AND CAST(ft.Vencimiento AS DATE) < @Hoy
    ),
    -- ----------------------------------------------------------------
    -- 4. INTERESES PENDIENTES (ND tipo 12 no canceladas)
    -- ----------------------------------------------------------------
    InteresesPendientes AS (
        SELECT ISNULL(SUM(nd.Valor), 0) AS interesesPendientes
        FROM dbo.Cxc nd
        LEFT JOIN (
            SELECT d.idCxcDebito, SUM(d.Valor) AS pagado
            FROM dbo.CxcDet d
            GROUP BY d.idCxcDebito
        ) pagNd ON pagNd.idCxcDebito = nd.idCxc
        WHERE nd.idTipoDocumento = 'ND'
          AND nd.idCxcTipo = 12
          AND nd.Cancelado = 0
    )
    SELECT
        -- Cartera Activa
        ISNULL(ca.capitalPendiente, 0)  AS capitalPendiente,
        ISNULL(ca.capitalOriginal, 0)   AS capitalOriginal,
        ISNULL(ca.totalPrestamos, 0)    AS totalPrestamos,

        -- Cobros del Mes
        ISNULL(cm.capitalCobrado, 0)    AS capitalCobradoMes,
        ISNULL(cm.interesCobrado, 0)    AS interesCobradoMes,
        ISNULL(cm.moraCobrada, 0)       AS moraCobradaMes,
        ISNULL(cm.totalCobrado, 0)      AS totalCobradoMes,
        ISNULL(cm.cantidadRecibos, 0)   AS recibosMes,

        -- Cartera Vencida
        ISNULL(pa.prestamosAtrasados, 0) AS prestamosAtrasados,
        CASE
            WHEN ISNULL(ca.totalPrestamos, 0) > 0
            THEN CAST(ISNULL(pa.prestamosAtrasados, 0) AS DECIMAL(10,4)) /
                 CAST(ca.totalPrestamos AS DECIMAL(10,4)) * 100.0
            ELSE 0
        END AS tasaMora,

        -- Intereses/Moras pendientes
        ISNULL(ip.interesesPendientes, 0) AS interesesPendientes,
        0.00                              AS morasPendientes,

        -- Metadata
        @InicioMes  AS periodoInicio,
        @FinMes     AS periodoFin,
        GETDATE()   AS generadoEn

    FROM CarteraActiva ca
    CROSS JOIN CobrosDelMes cm
    CROSS JOIN PrestamosAtrasados pa
    CROSS JOIN InteresesPendientes ip;
END
GO
