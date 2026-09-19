-- ============================================================
-- SP: cxcCobrosporMes  (v2 - columnas reales)
-- ============================================================
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
            DATEFROMPARTS(YEAR(rc.Fecha), MONTH(rc.Fecha), 1) AS mesFecha,
            -- Capital = aplicaciones a FT directamente
            SUM(CASE WHEN d.Referencia LIKE 'RP:%'
                     THEN d.Valor ELSE 0 END)               AS capitalCobrado,
            -- Interés = aplicaciones a ND
            SUM(CASE WHEN d.Referencia LIKE 'APL. INTERES%'
                     THEN d.Valor ELSE 0 END)               AS interesCobrado,
            0.00                                            AS moraCobrada,
            SUM(rc.Valor)                                   AS totalCobrado,
            COUNT(DISTINCT rc.idCxc)                        AS cantidadRecibos
        FROM dbo.Cxc rc
        INNER JOIN dbo.CxcDet d ON d.idCxc = rc.idCxc
        WHERE rc.idTipoDocumento = 'RC'
          AND rc.Cancelado = 0
          AND CAST(rc.Fecha AS DATE) >= @FechaInicio
        GROUP BY DATEFROMPARTS(YEAR(rc.Fecha), MONTH(rc.Fecha), 1)
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
