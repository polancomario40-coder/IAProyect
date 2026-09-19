-- ============================================================
-- SP: cxcEstadoPrestamo  (v2 - columnas reales confirmadas)
-- ============================================================
-- Estructura real:
--   Cxc.idCxc          UNIQUEIDENTIFIER (PK guid)
--   Cxc.Cxc            VARCHAR          (número visible ej. '17481')
--   Cxc.idDocumento    VARCHAR          (número texto)
--   Cxc.Valor          DECIMAL          (monto original)
--   Cxc.Cancelado      BIT
--   Cxc.Referencia     UNIQUEIDENTIFIER (guid del padre para ND/RC)
--   Cxc.Vencimiento    DATETIME
--   Cxc.Tasa           FLOAT            (tasa de interés)
--   Cxc.Usuario        VARCHAR          (creador)
--   Cxc.Cliente        VARCHAR          (nombre denormalizado)
--   Cxc.idCliente      INT
--   CxcDet.idCxc       UNIQUEIDENTIFIER (el RC)
--   CxcDet.idCxcDebito UNIQUEIDENTIFIER (el documento saldado)
--   CxcDet.Valor       DECIMAL
--   CxcDet.Referencia  VARCHAR  'APL. INTERES RECIBO #N' / 'RP:N|P:N|C:N'
-- ============================================================
USE Financiera
GO

IF OBJECT_ID('dbo.cxcEstadoPrestamo', 'P') IS NOT NULL
    DROP PROCEDURE dbo.cxcEstadoPrestamo
GO

CREATE PROCEDURE dbo.cxcEstadoPrestamo
    @numeroCxc VARCHAR(50)   -- numero visible del préstamo, ej. '17481'
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @Hoy DATE = CAST(GETDATE() AS DATE);

    -- Obtener el GUID del préstamo a partir del numero visible
    DECLARE @idCxc UNIQUEIDENTIFIER;
    SELECT @idCxc = idCxc
    FROM dbo.Cxc
    WHERE Cxc = @numeroCxc
      AND idTipoDocumento = 'FT'
      AND esCxc = 1;

    IF @idCxc IS NULL
    BEGIN
        -- Retornar 4 result sets vacíos para que el backend no falle
        SELECT CAST(NULL AS VARCHAR(50)) AS numeroPrestamo WHERE 1=0;
        SELECT CAST(NULL AS INT) AS numCuota WHERE 1=0;
        SELECT CAST(NULL AS INT) AS numeroPago WHERE 1=0;
        SELECT CAST(0 AS INT) AS totalCuotas, CAST(0 AS INT) AS totalRecibos;
        RETURN;
    END

    -- ================================================================
    -- RS 1: ENCABEZADO + 4 BLOQUES
    -- ================================================================
    ;WITH FT AS (
        SELECT idCxc, Cxc, idCliente, Cliente, Fecha, Valor, Tasa, Usuario,
               Concepto, Cancelado, Vencimiento
        FROM dbo.Cxc
        WHERE idCxc = @idCxc
    ),
    -- Intereses originales emitidos para este préstamo (ND tipo 12)
    InteresesEmitidos AS (
        SELECT ISNULL(SUM(nd.Valor), 0) AS interesInicial
        FROM dbo.Cxc nd
        WHERE nd.Referencia = @idCxc
          AND nd.idTipoDocumento = 'ND'
          AND nd.idCxcTipo = 12
          AND nd.Cancelado = 0
    ),
    -- Lo pagado (RC aplicados al préstamo FT y sus ND)
    PagosFT AS (
        -- Capital: CxcDet donde idCxcDebito = FT guid
        SELECT
            SUM(CASE WHEN d.idCxcDebito = @idCxc THEN d.Valor ELSE 0 END) AS capitalPagado,
            -- Interés: CxcDet donde idCxcDebito es un ND tipo 12 de este préstamo
            SUM(CASE WHEN nd.idCxc IS NOT NULL THEN d.Valor ELSE 0 END)   AS interesPagado
        FROM dbo.CxcDet d
        INNER JOIN dbo.Cxc rc ON rc.idCxc = d.idCxc AND rc.idTipoDocumento = 'RC' AND rc.Cancelado = 0
        LEFT JOIN dbo.Cxc nd  ON nd.idCxc = d.idCxcDebito
                              AND nd.idTipoDocumento = 'ND'
                              AND nd.idCxcTipo = 12
                              AND nd.Referencia = @idCxc
    ),
    -- Balance: capital restante
    BalanceFT AS (
        SELECT
            ft.Valor - ISNULL(pf.capitalPagado, 0)    AS capitalBalance,
            ISNULL(ie.interesInicial, 0) - ISNULL(pf.interesPagado, 0) AS interesBalance
        FROM FT ft
        CROSS JOIN PagosFT pf
        CROSS JOIN InteresesEmitidos ie
    ),
    -- Estado
    EstadoFT AS (
        SELECT
            CASE
                WHEN bf.capitalBalance <= 0 THEN 'AL DIA'
                WHEN CAST(ft.Vencimiento AS DATE) < @Hoy THEN 'ATRASADO'
                ELSE 'AL DIA'
            END AS estado,
            bf.capitalBalance,
            bf.interesBalance,
            CASE WHEN bf.capitalBalance > 0 AND CAST(ft.Vencimiento AS DATE) < @Hoy
                 THEN bf.capitalBalance ELSE 0 END AS capitalVencido
        FROM FT ft, BalanceFT bf
    )
    SELECT
        ft.Cxc                                          AS numeroPrestamo,
        ft.Cliente                                      AS nombreCliente,
        CAST(ft.Fecha AS DATE)                          AS fechaPrestamo,
        GETDATE()                                       AS fechaConsulta,
        ef.estado,

        -- Bloque INICIAL
        ft.Valor                                        AS capitalInicial,
        ISNULL(ie.interesInicial, 0)                   AS interesInicial,
        ft.Valor + ISNULL(ie.interesInicial, 0)        AS totalInicial,

        -- Bloque PAGADO
        ISNULL(pf.capitalPagado, 0)                    AS capitalPagado,
        ISNULL(pf.interesPagado, 0)                    AS interesPagado,
        0.00                                           AS moraPagada,
        ISNULL(pf.capitalPagado, 0) + ISNULL(pf.interesPagado, 0) AS totalPagado,

        -- Bloque BALANCE
        bf.capitalBalance                              AS capitalBalance,
        CASE WHEN bf.interesBalance > 0 THEN bf.interesBalance ELSE 0 END AS interesBalance,
        0.00                                           AS moraBalance,
        bf.capitalBalance + CASE WHEN bf.interesBalance > 0 THEN bf.interesBalance ELSE 0 END AS totalBalance,

        -- Bloque VENCIDO
        ef.capitalVencido,
        0.00                                           AS interesVencido,
        0.00                                           AS moraVencida,
        ef.capitalVencido                              AS totalVencido,

        -- Meta
        0                                              AS cuotasVencidas,
        ft.Tasa                                        AS tasaInteres,
        ft.Usuario                                     AS creador,
        ft.Concepto                                    AS tipoPrestamo

    FROM FT ft
    CROSS JOIN InteresesEmitidos ie
    CROSS JOIN PagosFT pf
    CROSS JOIN BalanceFT bf
    CROSS JOIN EstadoFT ef;


    -- ================================================================
    -- RS 2: CUOTAS (pagos realizados como líneas de cuota)
    -- ================================================================
    ;WITH PagosAgrupados AS (
        SELECT
            rc.idCxc,
            rc.Cxc                                              AS numRecibo,
            rc.Fecha,
            SUM(CASE WHEN d.idCxcDebito = @idCxc
                     THEN d.Valor ELSE 0 END)                  AS capital,
            SUM(CASE WHEN d.Referencia LIKE 'APL. INTERES%'
                     THEN d.Valor ELSE 0 END)                  AS interes
        FROM dbo.Cxc rc
        INNER JOIN dbo.CxcDet d ON d.idCxc = rc.idCxc
        WHERE rc.idTipoDocumento = 'RC'
          AND rc.Cancelado = 0
          AND EXISTS (
              SELECT 1 FROM dbo.CxcDet dx
              WHERE dx.idCxc = rc.idCxc
                AND (dx.idCxcDebito = @idCxc
                  OR EXISTS (
                      SELECT 1 FROM dbo.Cxc nd
                      WHERE nd.idCxc = dx.idCxcDebito
                        AND nd.Referencia = @idCxc
                        AND nd.idTipoDocumento = 'ND'
                  ))
          )
        GROUP BY rc.idCxc, rc.Cxc, rc.Fecha
    ),
    CapitalInicial AS (
        SELECT Valor FROM dbo.Cxc WHERE idCxc = @idCxc
    )
    SELECT
        ROW_NUMBER() OVER (ORDER BY pa.Fecha)           AS numCuota,
        pa.idCxc                                        AS idCuota,
        CAST(pa.Fecha AS DATE)                          AS fecha,
        ci.Valor - SUM(pa.capital) OVER (
            ORDER BY pa.Fecha
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )                                               AS balance,
        pa.capital,
        pa.interes,
        0.00                                            AS mora,
        'PAGADA'                                        AS estadoCuota
    FROM PagosAgrupados pa
    CROSS JOIN CapitalInicial ci
    ORDER BY pa.Fecha;


    -- ================================================================
    -- RS 3: HISTORIAL DE RECIBOS (Pagos)
    -- ================================================================
    ;WITH DetConTipo AS (
        -- Clasificamos cada línea de CxcDet: capital o interés
        SELECT
            d.idCxc                                    AS idRc,
            d.idCxcDebito,
            d.Valor,
            CASE
                WHEN d.idCxcDebito = @idCxc THEN 'CAPITAL'
                WHEN nd.idCxc IS NOT NULL   THEN 'INTERES'
                ELSE 'OTRO'
            END                                        AS tipoApl
        FROM dbo.CxcDet d
        -- JOIN opcional a ND para identificar líneas de interés
        LEFT JOIN dbo.Cxc nd ON nd.idCxc = d.idCxcDebito
                             AND nd.idTipoDocumento = 'ND'
                             AND nd.idCxcTipo = 12
                             AND nd.Referencia = @idCxc
        WHERE d.idCxcDebito = @idCxc
           OR (nd.idCxc IS NOT NULL)
    ),
    ResumenRC AS (
        SELECT
            idRc,
            SUM(CASE WHEN tipoApl = 'CAPITAL' THEN Valor ELSE 0 END) AS capital,
            SUM(CASE WHEN tipoApl = 'INTERES' THEN Valor ELSE 0 END) AS interes
        FROM DetConTipo
        GROUP BY idRc
    )
    SELECT
        rc.Cxc                                         AS numeroPago,
        CAST(rc.Fecha AS DATE)                         AS fecha,
        rc.Valor                                       AS totalPagado,
        ISNULL(rr.capital, 0)                          AS capital,
        ISNULL(rr.interes, 0)                          AS interes,
        0.00                                           AS mora,
        rc.Usuario                                     AS usuario,
        rc.Concepto                                    AS observacion
    FROM dbo.Cxc rc
    INNER JOIN ResumenRC rr ON rr.idRc = rc.idCxc
    WHERE rc.idTipoDocumento = 'RC'
      AND rc.Cancelado = 0
    ORDER BY rc.Fecha DESC;


    -- ================================================================
    -- RS 4: CONTEOS
    -- ================================================================
    SELECT
        (SELECT COUNT(*) FROM dbo.Cxc rc
          WHERE rc.idTipoDocumento = 'RC' AND rc.Cancelado = 0
            AND EXISTS (SELECT 1 FROM dbo.CxcDet dx WHERE dx.idCxc = rc.idCxc AND dx.idCxcDebito = @idCxc)
        ) AS totalCuotas,
        (SELECT COUNT(*) FROM dbo.Cxc rc
          WHERE rc.idTipoDocumento = 'RC' AND rc.Cancelado = 0
            AND EXISTS (SELECT 1 FROM dbo.CxcDet dx WHERE dx.idCxc = rc.idCxc AND dx.idCxcDebito = @idCxc)
        ) AS totalRecibos;
END
GO
