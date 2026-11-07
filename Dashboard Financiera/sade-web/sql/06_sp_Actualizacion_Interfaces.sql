-- =========================================================================================
-- SP: ACTUALIZACION DE PROCEDIMIENTOS DE INTERFAZ DE TAREAS WINDOWS (Solonegocios -> Financiera)
-- Versión Ultra-Optimizada (Sin bloqueos, sin subconsultas pesadas, 100% velocidad original)
-- =========================================================================================
USE Financiera
GO

-- -----------------------------------------------------------------------------------------
-- 1. IntfPrestamo2Cxc (Ultra-rápido, indexado por idDocumento)
-- -----------------------------------------------------------------------------------------
IF OBJECT_ID('dbo.IntfPrestamo2Cxc', 'P') IS NOT NULL
    DROP PROCEDURE dbo.IntfPrestamo2Cxc
GO

CREATE PROCEDURE [dbo].[IntfPrestamo2Cxc]
AS
BEGIN
    SET NOCOUNT ON;
    SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

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
        CASE WHEN P.pr_estado = 1 THEN 0 ELSE 1 END,
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
    FROM dbsolonegocios.dbo.tb_prestamos P WITH (NOLOCK)
    INNER JOIN (
        SELECT dp_id_prestamos, SUM(dp_capital) AS CapitalOriginal, MAX(dp_fecha_venc) AS FechaVencimiento
        FROM dbsolonegocios.dbo.tb_detalle_prestamos WITH (NOLOCK)
        WHERE dp_estado <> 0
        GROUP BY dp_id_prestamos
    ) D ON D.dp_id_prestamos = P.pr_id_prestamos
    INNER JOIN dbo.Cliente C WITH (NOLOCK) ON C.idCliente = P.pr_id_cliente
    WHERE ISNULL(P.pr_estado, 0) <> 0
      AND NOT EXISTS (
          SELECT 1 FROM dbo.Cxc X WITH (NOLOCK) WHERE X.idDocumento = CAST(P.pr_id_prestamos AS VARCHAR(20)) AND X.idTipoDocumento = 'FT'
      );

    -- 2. SINCRONIZAR ESTADO DE PRESTAMOS QUE YA FUERON SALDADOS O CANCELADOS EN SOLONEGOCIOS
    -- Utiliza búsqueda exacta indexada por idDocumento sin scans ni bloqueos
    UPDATE c
    SET c.Cancelado = 1
    FROM dbo.Cxc c
    INNER JOIN dbsolonegocios.dbo.tb_prestamos p WITH (NOLOCK)
        ON c.idDocumento = CAST(p.pr_id_prestamos AS VARCHAR(20))
        AND c.idTipoDocumento = 'FT'
    WHERE c.Cancelado = 0
      AND (p.pr_estado <> 1 OR ISNULL(p.pr_balance, 0) <= 0);

    -- 3. REACTIVAR SI UN PRESTAMO ESTA ACTIVO VIGENTE
    UPDATE c
    SET c.Cancelado = 0
    FROM dbo.Cxc c
    INNER JOIN dbsolonegocios.dbo.tb_prestamos p WITH (NOLOCK)
        ON c.idDocumento = CAST(p.pr_id_prestamos AS VARCHAR(20))
        AND c.idTipoDocumento = 'FT'
    WHERE c.Cancelado = 1
      AND p.pr_estado = 1
      AND ISNULL(p.pr_balance, 0) > 0;
END
GO

-- -----------------------------------------------------------------------------------------
-- 2. IntfReciboPrestamo2Cxc (Ultra-rápido, indexado)
-- -----------------------------------------------------------------------------------------
IF OBJECT_ID('dbo.IntfReciboPrestamo2Cxc', 'P') IS NOT NULL
    DROP PROCEDURE dbo.IntfReciboPrestamo2Cxc
GO

CREATE PROCEDURE [dbo].[IntfReciboPrestamo2Cxc]
AS
BEGIN
    SET NOCOUNT ON;
    SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

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
    FROM dbsolonegocios.dbo.tb_recibo_pagos r WITH (NOLOCK)
    INNER JOIN dbo.Cxc f WITH (NOLOCK)
        ON f.idDocumento = CAST(r.rp_id_prestamo AS VARCHAR(20))
        AND f.idTipoDocumento = 'FT'
        AND f.idCxcTipo = -1
    INNER JOIN dbo.Cliente c WITH (NOLOCK)
        ON c.idCliente = ISNULL(r.rp_id_cliente, f.idCliente)
    WHERE ISNULL(r.rp_total_pagado, 0) > 0
      AND ISNULL(r.rp_estado, 1) = 1
      AND UPPER(LTRIM(RTRIM(ISNULL(r.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
      AND NOT EXISTS (
          SELECT 1 FROM dbo.Cxc x WITH (NOLOCK)
          WHERE x.idDocumento = CAST(r.rp_id_recibo AS VARCHAR(20))
            AND x.idTipoDocumento = 'RC'
      );
END
GO

-- -----------------------------------------------------------------------------------------
-- 3. IntfSincronizarInteresMora2Cxc (Optimizado con búsqueda indexada directa)
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

        -- 1. CREACIÓN DE NUEVAS NOTAS DE DÉBITO (INTERÉS Y MORA)
        INSERT INTO dbo.Cxc (
            idCxc, Cxc, idCliente, idTipoDocumento, Valor, Fecha, Concepto, idCxcTipo, esCredito, Cancelado, Cliente, 
            Usuario, idDocumento, Descuento, Condicion, Vencimiento, idMoneda, Tasa, recibido, PendValidacion, PendEnvioEcf, StatusEcf, Referencia
        )
        SELECT 
            NEWID(), 'INT-' + CAST(rp.rp_id_recibo AS VARCHAR(20)), rc.idCliente, 'ND', rp.rp_interes, rp.rp_fecha, 
            'INTERESES DEL RECIBO #' + CAST(rp.rp_id_recibo AS VARCHAR(20)) + ' REF: PRESTAMO ' + CAST(rp.rp_id_prestamo AS VARCHAR(20)), 
            @idCxcTipo_Interes, 0, 0, rc.Cliente, rc.Usuario, 'INT-' + CAST(rp.rp_id_recibo AS VARCHAR(20)), 
            0, 30, rp.rp_fecha, 1, 1, 0, 0, 0, 'PENDIENTE', ft.idCxc
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp WITH (NOLOCK)
        JOIN dbo.Cxc rc WITH (NOLOCK) ON rc.idDocumento = CAST(rp.rp_id_recibo AS VARCHAR(20)) AND rc.idTipoDocumento = 'RC'
        LEFT JOIN dbo.Cxc ft WITH (NOLOCK) ON ft.idDocumento = CAST(rp.rp_id_prestamo AS VARCHAR(20)) AND ft.idTipoDocumento = 'FT'
        WHERE ISNULL(rp.rp_interes, 0) > 0 AND rp.rp_estado = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
          AND NOT EXISTS (SELECT 1 FROM dbo.Cxc nd WITH (NOLOCK) WHERE nd.idDocumento = 'INT-' + CAST(rp.rp_id_recibo AS VARCHAR(20)) AND nd.idTipoDocumento = 'ND');

        INSERT INTO dbo.Cxc (
            idCxc, Cxc, idCliente, idTipoDocumento, Valor, Fecha, Concepto, idCxcTipo, esCredito, Cancelado, Cliente, 
            Usuario, idDocumento, Descuento, Condicion, Vencimiento, idMoneda, Tasa, recibido, PendValidacion, PendEnvioEcf, StatusEcf, Referencia
        )
        SELECT 
            NEWID(), 'MOR-' + CAST(rp.rp_id_recibo AS VARCHAR(20)), rc.idCliente, 'ND', rp.rp_mora, rp.rp_fecha, 
            'MORA DEL RECIBO #' + CAST(rp.rp_id_recibo AS VARCHAR(20)) + ' REF: PRESTAMO ' + CAST(rp.rp_id_prestamo AS VARCHAR(20)), 
            @idCxcTipo_Mora, 0, 0, rc.Cliente, rc.Usuario, 'MOR-' + CAST(rp.rp_id_recibo AS VARCHAR(20)), 
            0, 30, rp.rp_fecha, 1, 1, 0, 0, 0, 'PENDIENTE', ft.idCxc
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp WITH (NOLOCK)
        JOIN dbo.Cxc rc WITH (NOLOCK) ON rc.idDocumento = CAST(rp.rp_id_recibo AS VARCHAR(20)) AND rc.idTipoDocumento = 'RC'
        LEFT JOIN dbo.Cxc ft WITH (NOLOCK) ON ft.idDocumento = CAST(rp.rp_id_prestamo AS VARCHAR(20)) AND ft.idTipoDocumento = 'FT'
        WHERE ISNULL(rp.rp_mora, 0) > 0 AND rp.rp_estado = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
          AND NOT EXISTS (SELECT 1 FROM dbo.Cxc nd WITH (NOLOCK) WHERE nd.idDocumento = 'MOR-' + CAST(rp.rp_id_recibo AS VARCHAR(20)) AND nd.idTipoDocumento = 'ND');

        -- 2. APLICACIÓN DE PAGOS (CxcDet)
        INSERT INTO dbo.CxcDet (idCxcDet, idCxc, idCxcDebito, Valor, Fecha, Descuento, Tasa, Referencia)
        SELECT NEWID(), rc.idCxc, nd.idCxc, rp.rp_interes, rc.Fecha, 0, rc.Tasa, 'APL. INTERES RECIBO #' + CAST(rp.rp_id_recibo AS VARCHAR(20))
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp WITH (NOLOCK)
        JOIN dbo.Cxc rc WITH (NOLOCK) ON rc.idDocumento = CAST(rp.rp_id_recibo AS VARCHAR(20)) AND rc.idTipoDocumento = 'RC'
        JOIN dbo.Cxc nd WITH (NOLOCK) ON nd.idDocumento = 'INT-' + CAST(rp.rp_id_recibo AS VARCHAR(20)) AND nd.idTipoDocumento = 'ND'
        WHERE ISNULL(rp.rp_interes, 0) > 0 AND rp.rp_estado = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
          AND NOT EXISTS (SELECT 1 FROM dbo.CxcDet cd WITH (NOLOCK) WHERE cd.idCxc = rc.idCxc AND cd.idCxcDebito = nd.idCxc);

        INSERT INTO dbo.CxcDet (idCxcDet, idCxc, idCxcDebito, Valor, Fecha, Descuento, Tasa, Referencia)
        SELECT NEWID(), rc.idCxc, nd.idCxc, rp.rp_mora, rc.Fecha, 0, rc.Tasa, 'APL. MORA RECIBO #' + CAST(rp.rp_id_recibo AS VARCHAR(20))
        FROM dbsolonegocios.dbo.tb_recibo_pagos rp WITH (NOLOCK)
        JOIN dbo.Cxc rc WITH (NOLOCK) ON rc.idDocumento = CAST(rp.rp_id_recibo AS VARCHAR(20)) AND rc.idTipoDocumento = 'RC'
        JOIN dbo.Cxc nd WITH (NOLOCK) ON nd.idDocumento = 'MOR-' + CAST(rp.rp_id_recibo AS VARCHAR(20)) AND nd.idTipoDocumento = 'ND'
        WHERE ISNULL(rp.rp_mora, 0) > 0 AND rp.rp_estado = 1
          AND UPPER(LTRIM(RTRIM(ISNULL(rp.rp_forma_pago, '')))) NOT IN ('N.CREDITO', 'N. CREDITO', 'NOTA DE CREDITO', 'NC')
          AND NOT EXISTS (SELECT 1 FROM dbo.CxcDet cd WITH (NOLOCK) WHERE cd.idCxc = rc.idCxc AND cd.idCxcDebito = nd.idCxc);

        -- 3. GENERACIÓN DE CODIFICACIÓN CONTABLE AUTOMÁTICA
        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), nd.idCxc, '10105001', 1, nd.Valor, 'ASIENTO INTERES', 1, 'ND', nd.Fecha FROM dbo.Cxc nd WITH (NOLOCK)
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'INTERESES DEL RECIBO %' AND nd.idCxcTipo = @idCxcTipo_Interes
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WITH (NOLOCK) WHERE cg.GUIDDocumento = nd.idCxc AND cg.DebCre = 1);

        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), nd.idCxc, '42401', 2, nd.Valor, 'ASIENTO INTERES', 1, 'ND', nd.Fecha FROM dbo.Cxc nd WITH (NOLOCK)
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'INTERESES DEL RECIBO %' AND nd.idCxcTipo = @idCxcTipo_Interes
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WITH (NOLOCK) WHERE cg.GUIDDocumento = nd.idCxc AND cg.DebCre = 2);

        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), nd.idCxc, '10105002', 1, nd.Valor, 'ASIENTO MORA', 1, 'ND', nd.Fecha FROM dbo.Cxc nd WITH (NOLOCK)
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'MORA DEL RECIBO %' AND nd.idCxcTipo = @idCxcTipo_Mora
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WITH (NOLOCK) WHERE cg.GUIDDocumento = nd.idCxc AND cg.DebCre = 1);

        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), nd.idCxc, '42501', 2, nd.Valor, 'ASIENTO MORA', 1, 'ND', nd.Fecha FROM dbo.Cxc nd WITH (NOLOCK)
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'MORA DEL RECIBO %' AND nd.idCxcTipo = @idCxcTipo_Mora
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WITH (NOLOCK) WHERE cg.GUIDDocumento = nd.idCxc AND cg.DebCre = 2);

        -- RECLASIFICACIÓN DE APLICACIÓN
        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), cd.idCxcDet, '10102001', 1, cd.TotalAplicado, 'APLICACION INTERES', 1, 'AP', cd.Fecha 
        FROM dbo.CxcDet cd WITH (NOLOCK) JOIN dbo.Cxc nd WITH (NOLOCK) ON cd.idCxcDebito = nd.idCxc
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'INTERESES DEL RECIBO %'
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WITH (NOLOCK) WHERE cg.GUIDDocumento = cd.idCxcDet AND cg.DebCre = 1);

        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), cd.idCxcDet, '10105001', 2, cd.TotalAplicado, 'APLICACION INTERES', 1, 'AP', cd.Fecha 
        FROM dbo.CxcDet cd WITH (NOLOCK) JOIN dbo.Cxc nd WITH (NOLOCK) ON cd.idCxcDebito = nd.idCxc
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'INTERESES DEL RECIBO %'
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WITH (NOLOCK) WHERE cg.GUIDDocumento = cd.idCxcDet AND cg.DebCre = 2);

        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), cd.idCxcDet, '10102001', 1, cd.TotalAplicado, 'APLICACION MORA', 1, 'AP', cd.Fecha 
        FROM dbo.CxcDet cd WITH (NOLOCK) JOIN dbo.Cxc nd WITH (NOLOCK) ON cd.idCxcDebito = nd.idCxc
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'MORA DEL RECIBO %'
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WITH (NOLOCK) WHERE cg.GUIDDocumento = cd.idCxcDet AND cg.DebCre = 1);

        INSERT INTO dbo.cgCodificacion (idCodificacion, GUIDDocumento, idCuenta, DebCre, Valor, Referencia, Automatica, TipoDocumento, Fecha)
        SELECT NEWID(), cd.idCxcDet, '10105002', 2, cd.TotalAplicado, 'APLICACION MORA', 1, 'AP', cd.Fecha 
        FROM dbo.CxcDet cd WITH (NOLOCK) JOIN dbo.Cxc nd WITH (NOLOCK) ON cd.idCxcDebito = nd.idCxc
        WHERE nd.idTipoDocumento = 'ND' AND nd.Concepto LIKE 'MORA DEL RECIBO %'
          AND NOT EXISTS (SELECT 1 FROM dbo.cgCodificacion cg WITH (NOLOCK) WHERE cg.GUIDDocumento = cd.idCxcDet AND cg.DebCre = 2);

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END
GO
