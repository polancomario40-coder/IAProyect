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
