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
