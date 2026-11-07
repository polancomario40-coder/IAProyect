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
