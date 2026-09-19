-- ============================================================
-- SP: cxcClientesIntelligence  (v2 - usando #temp para multi-RS)
-- ============================================================
USE Financiera
GO

IF OBJECT_ID('dbo.cxcClientesIntelligence', 'P') IS NOT NULL
    DROP PROCEDURE dbo.cxcClientesIntelligence
GO

CREATE PROCEDURE dbo.cxcClientesIntelligence
    @fechaDesde  DATE        = NULL,
    @fechaHasta  DATE        = NULL,
    @empresa     VARCHAR(200)= NULL,
    @estado      VARCHAR(30) = NULL,
    @busqueda    VARCHAR(200)= NULL,
    @oficina     VARCHAR(100)= NULL,
    @gestor      VARCHAR(100)= NULL,
    @pagina      INT         = 1,
    @porPagina   INT         = 25
AS
BEGIN
    SET NOCOUNT ON;

    SET @fechaHasta = ISNULL(@fechaHasta, CAST(GETDATE() AS DATE));
    SET @pagina     = ISNULL(@pagina, 1);
    SET @porPagina  = ISNULL(@porPagina, 25);

    DECLARE @offset INT = (@pagina - 1) * @porPagina;

    -- ── Tabla temporal con todos los datos clasificados ──────────────
    CREATE TABLE #Clasificados (
        idCliente        INT,
        nombreCompleto   VARCHAR(200),
        cedula           VARCHAR(30),
        telefono         VARCHAR(30),
        correo           VARCHAR(100),
        direccion        VARCHAR(500),
        oficina          VARCHAR(100),
        fechaRegistro    DATE,
        idEmpresa        INT,
        empresa          VARCHAR(200),
        cargoEmpresa     VARCHAR(100),
        fechaIngresoEmpresa DATE,
        salario          DECIMAL(18,2),
        gestor           VARCHAR(100),
        supervisor       VARCHAR(100),
        sexo             VARCHAR(5),
        esProblematico   BIT,
        banco            VARCHAR(100),
        cuentaBancaria   VARCHAR(50),
        totalPrestamos   INT,
        prestamosActivos INT,
        primerPrestamo   DATETIME,
        ultimoPrestamo   DATETIME,
        montoHistorico   DECIMAL(18,2),
        numeroPrestamo   VARCHAR(50),
        montoActual      DECIMAL(18,2),
        tasa             FLOAT,
        fechaPrestamo    DATETIME,
        vencimiento      DATETIME,
        capitalPagado    DECIMAL(18,2),
        balanceActual    DECIMAL(18,2),
        clasificacion    VARCHAR(20)
    );

    -- ── Cargar datos desde dbsolonegocios + Financiera ───────────────
    INSERT INTO #Clasificados
    SELECT
        vc.CODIGO,
        vc.NOMBRE_COMPLETO,
        vc.IDENTIDAD,
        vc.CELULAR,
        vc.CORREO,
        vc.DIRECCION,
        vc.OFICINA,
        CAST(vc.FECHA_REGISTRO AS DATE),
        vc.ID_EMPRESA,
        vc.EMPRESA,
        vc.POSICION,
        TRY_CAST(vc.FECHA_INGRESO AS DATE),
        CAST(ISNULL(vc.SALARIO, 0) AS DECIMAL(18,2)),
        vc.GESTOR,
        vc.SUPERVISOR,
        vc.SEXO,
        vc.PROBLEMATICO,
        vc.BANCO,
        vc.CUENTA,
        -- Conteo préstamos
        ISNULL(cp.totalPrestamos,   0),
        ISNULL(cp.prestamosActivos, 0),
        cp.primerPrestamo,
        cp.ultimoPrestamo,
        ISNULL(cp.montoHistorico, 0),
        -- Préstamo activo en Financiera
        ec.numeroPrestamo,
        ec.montoActual,
        ec.tasa,
        ec.fechaPrestamo,
        ec.vencimiento,
        ISNULL(ec.capitalPagado, 0),
        ISNULL(ec.montoActual, 0) - ISNULL(ec.capitalPagado, 0),
        -- Clasificación
        CASE
            WHEN vc.PROBLEMATICO = 1
                THEN 'PROBLEMATICO'
            WHEN ec.vencimiento IS NOT NULL
             AND CAST(ec.vencimiento AS DATE) < CAST(GETDATE() AS DATE)
             AND (ISNULL(ec.montoActual, 0) - ISNULL(ec.capitalPagado, 0)) > 0
                THEN 'EN MORA'
            WHEN ISNULL(cp.totalPrestamos, 0) <= 1
                THEN 'NUEVO'
            WHEN ISNULL(cp.totalPrestamos, 0) > 1
                THEN 'REENGANCHADO'
            ELSE 'AL DIA'
        END
    FROM dbsolonegocios.dbo.vw_datos_clientes vc
    LEFT JOIN (
        SELECT
            pr.pr_id_cliente,
            COUNT(*)                                            AS totalPrestamos,
            SUM(CASE WHEN pr.pr_estado=1 THEN 1 ELSE 0 END)   AS prestamosActivos,
            MIN(pr.pr_fecha)                                    AS primerPrestamo,
            MAX(pr.pr_fecha)                                    AS ultimoPrestamo,
            SUM(CAST(pr.pr_monto AS DECIMAL(18,2)))            AS montoHistorico
        FROM dbsolonegocios.dbo.tb_prestamos pr
        GROUP BY pr.pr_id_cliente
    ) cp ON cp.pr_id_cliente = vc.CODIGO
    LEFT JOIN (
        SELECT
            ft.idCliente,
            MAX(ft.Cxc)                                         AS numeroPrestamo,
            MAX(CAST(ft.Valor AS DECIMAL(18,2)))               AS montoActual,
            MAX(ft.Tasa)                                        AS tasa,
            MAX(ft.Fecha)                                       AS fechaPrestamo,
            MAX(ft.Vencimiento)                                 AS vencimiento,
            ISNULL(SUM(d.Valor), 0)                            AS capitalPagado
        FROM dbo.Cxc ft
        LEFT JOIN dbo.CxcDet d ON d.idCxcDebito = ft.idCxc
        WHERE ft.idTipoDocumento = 'FT'
          AND ft.Cancelado = 0
          AND ft.esCxc = 1
        GROUP BY ft.idCliente
    ) ec ON ec.idCliente = vc.CODIGO
    WHERE
        -- Filtros
        (CAST(vc.FECHA_REGISTRO AS DATE) >= ISNULL(@fechaDesde, '2000-01-01'))
        AND (CAST(vc.FECHA_REGISTRO AS DATE) <= @fechaHasta)
        AND (@empresa IS NULL OR vc.EMPRESA LIKE '%' + @empresa + '%')
        AND (@oficina  IS NULL OR vc.OFICINA = @oficina)
        AND (@gestor   IS NULL OR vc.GESTOR LIKE '%' + @gestor + '%')
        AND (@busqueda IS NULL
             OR vc.NOMBRE_COMPLETO LIKE '%' + @busqueda + '%'
             OR vc.IDENTIDAD        LIKE '%' + @busqueda + '%'
             OR vc.CELULAR          LIKE '%' + @busqueda + '%');

    -- Aplicar filtro de estado DESPUÉS de clasificar
    IF @estado IS NOT NULL
        DELETE FROM #Clasificados WHERE clasificacion <> @estado;

    -- ── RS 1: KPIs / Estadísticas ────────────────────────────────────
    SELECT
        COUNT(*)                                                     AS totalClientes,
        SUM(CASE WHEN clasificacion='NUEVO'        THEN 1 ELSE 0 END) AS nuevos,
        SUM(CASE WHEN clasificacion='REENGANCHADO' THEN 1 ELSE 0 END) AS reenganchados,
        SUM(CASE WHEN clasificacion='EN MORA'      THEN 1 ELSE 0 END) AS enMora,
        SUM(CASE WHEN clasificacion='PROBLEMATICO' THEN 1 ELSE 0 END) AS problematicos,
        SUM(CASE WHEN clasificacion='AL DIA'       THEN 1 ELSE 0 END) AS alDia,
        ISNULL(SUM(montoActual), 0)                                  AS montoTotalCartera,
        ISNULL(SUM(balanceActual), 0)                                AS balanceTotalPendiente,
        @pagina                                                      AS paginaActual,
        @porPagina                                                   AS porPagina,
        CAST(CEILING(CAST(COUNT(*) AS FLOAT) / @porPagina) AS INT)  AS totalPaginas
    FROM #Clasificados;

    -- ── RS 2: Lista paginada ─────────────────────────────────────────
    SELECT
        idCliente, nombreCompleto, cedula, telefono, correo,
        oficina, fechaRegistro, empresa, cargoEmpresa, salario,
        gestor, sexo, esProblematico, banco, cuentaBancaria,
        totalPrestamos, prestamosActivos,
        primerPrestamo, ultimoPrestamo, montoHistorico,
        numeroPrestamo, montoActual, tasa, fechaPrestamo,
        vencimiento, capitalPagado, balanceActual, clasificacion
    FROM #Clasificados
    ORDER BY fechaRegistro DESC, idCliente
    OFFSET @offset ROWS FETCH NEXT @porPagina ROWS ONLY;

    -- ── RS 3: Top 15 empresas ────────────────────────────────────────
    SELECT TOP 15
        ISNULL(empresa, 'Sin Empresa')                               AS empresa,
        COUNT(*)                                                     AS totalClientes,
        SUM(CASE WHEN clasificacion='NUEVO'        THEN 1 ELSE 0 END) AS nuevos,
        SUM(CASE WHEN clasificacion='REENGANCHADO' THEN 1 ELSE 0 END) AS reenganchados,
        SUM(CASE WHEN clasificacion='EN MORA'      THEN 1 ELSE 0 END) AS enMora,
        ISNULL(SUM(balanceActual), 0)                                AS cartera
    FROM #Clasificados
    GROUP BY empresa
    ORDER BY totalClientes DESC;

    -- ── RS 4: Valores únicos para dropdowns de filtros ───────────────
    SELECT DISTINCT oficina FROM #Clasificados
    WHERE oficina IS NOT NULL ORDER BY oficina;

    DROP TABLE #Clasificados;
END
GO
