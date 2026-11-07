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
