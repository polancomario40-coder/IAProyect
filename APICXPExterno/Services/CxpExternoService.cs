using CxpApi.Data;
using CxpApi.Models;
using Microsoft.Data.SqlClient;

namespace CxpApi.Services;

public class CxpExternoService : ICxpExternoService
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<CxpExternoService> _logger;
    private readonly DgiiService _dgiiService;

    public CxpExternoService(IServiceProvider serviceProvider, ILogger<CxpExternoService> logger, DgiiService dgiiService)
    {
        _serviceProvider = serviceProvider;
        _logger = logger;
        _dgiiService = dgiiService;
    }

    public async Task<ResultadoOperacion> ProcesarFacturaExternaAsync(CxpFacturaExternaDto dto)
    {
        try
        {
            // 1. Math Validation
            decimal expectedTotal = dto.Subtotal + dto.Itbis + dto.Propina + dto.Isc + dto.OtrosImpuestos;
            if (dto.Total > 0 && expectedTotal != dto.Total)
            {
                return ResultadoOperacion.Fallido($"Error matemático: La suma de Subtotal e impuestos/propina ({expectedTotal}) no coincide con el Total enviado ({dto.Total}).");
            }

            // 2. Multi-company routing logic
            string connectionString = string.Empty;
            using (var scope = _serviceProvider.CreateScope())
            {
                var authDb = scope.ServiceProvider.GetRequiredService<AuthDbContext>();
                var empresa = authDb.Empresas.FirstOrDefault(e => e.BaseDatos == dto.BaseDatos && e.RNC == dto.RncCompania && e.Activa);

                if (empresa == null)
                {
                    return ResultadoOperacion.Fallido($"No se encontró una empresa activa con BaseDatos '{dto.BaseDatos}' y RNC '{dto.RncCompania}'.");
                }

                var erpConnectionProvider = scope.ServiceProvider.GetRequiredService<Providers.IErpConnectionProvider>();
                connectionString = erpConnectionProvider.GetConnectionString(empresa.IdEmpresa);
            }

            using var connection = new SqlConnection(connectionString);
            await connection.OpenAsync();

            // 2.5 Moneda string lookup (ej: "US$", "RD$")
            int finalIdMoneda = dto.IdMoneda > 0 ? dto.IdMoneda : 1;
            if (!string.IsNullOrEmpty(dto.Moneda))
            {
                using var cmdMonedaStr = connection.CreateCommand();
                cmdMonedaStr.CommandText = "SELECT TOP 1 idMoneda FROM Moneda WHERE moneda = @MonedaStr";
                cmdMonedaStr.Parameters.AddWithValue("@MonedaStr", dto.Moneda);
                var monRes = await cmdMonedaStr.ExecuteScalarAsync();
                if (monRes != null && monRes != DBNull.Value)
                {
                    finalIdMoneda = Convert.ToInt32(monRes);
                }
            }

            // 3. Supplier Validation
            using var cmdCheckSuplidor = connection.CreateCommand();
            cmdCheckSuplidor.CommandText = "SELECT TOP 1 IdSuplidor, Nombre, RNC, idTipoIdentificacion FROM cxpSuplidores WHERE RNC = @rnc AND Estatus = 1";
            cmdCheckSuplidor.Parameters.AddWithValue("@rnc", dto.RncSuplidor);
            
            int idSuplidor = 0;
            string nombreSuplidor = "";
            string rncSuplidor = dto.RncSuplidor;
            string tipoIdentificacion = "1"; // Default

            bool suplidorExiste = false;
            using (var reader = await cmdCheckSuplidor.ExecuteReaderAsync())
            {
                if (await reader.ReadAsync())
                {
                    idSuplidor = Convert.ToInt32(reader["IdSuplidor"]);
                    nombreSuplidor = reader["Nombre"]?.ToString() ?? "";
                    rncSuplidor = reader["RNC"]?.ToString() ?? dto.RncSuplidor;
                    tipoIdentificacion = reader["idTipoIdentificacion"]?.ToString() ?? "1";
                    suplidorExiste = true;
                }
            }

            if (!suplidorExiste)
            {
                // Prioridad del nombre: DTO > DGII > "Suplidor Generado Automáticamente"
                string nuevoNombreSuplidor = dto.NombreSuplidor ?? string.Empty;
                if (string.IsNullOrWhiteSpace(nuevoNombreSuplidor))
                {
                    var dgiiResult = await _dgiiService.ConsultarRncAsync(dto.RncSuplidor);
                    nuevoNombreSuplidor = (dgiiResult != null && dgiiResult.Encontrado && !string.IsNullOrWhiteSpace(dgiiResult.NombreComercial))
                        ? dgiiResult.NombreComercial
                        : "Suplidor Generado Automáticamente";
                }

                // Prevenir error de Foreign Key consultando valores válidos de catálogos
                using var cmdTipoSup = connection.CreateCommand();
                cmdTipoSup.CommandText = "SELECT TOP 1 TipoSuplidor FROM cxpTiposSuplidor ORDER BY TipoSuplidor";
                var tipoSupObj = await cmdTipoSup.ExecuteScalarAsync();
                int tipoSuplidorVal = (tipoSupObj != null && tipoSupObj != DBNull.Value) ? Convert.ToInt32(tipoSupObj) : 1;

                // Fallback por defecto (según la tabla del cliente: 2 = Compra, 8 = NO ITBIS)
                int tipoImpuestoVal = dto.Itbis > 0 ? 2 : 8; 
                
                using var cmdTipoImp = connection.CreateCommand();
                if (dto.Itbis <= 0)
                {
                    cmdTipoImp.CommandText = "SELECT TOP 1 TipoImpuesto FROM ocTiposImpuestos WHERE Descripcion LIKE '%NO ITBIS%'";
                }
                else if (dto.EsServicio)
                {
                    cmdTipoImp.CommandText = "SELECT TOP 1 TipoImpuesto FROM ocTiposImpuestos WHERE Descripcion LIKE '%Servicio%' AND Porcentaje > 0";
                }
                else
                {
                    cmdTipoImp.CommandText = "SELECT TOP 1 TipoImpuesto FROM ocTiposImpuestos WHERE Descripcion LIKE '%Compra%' AND Porcentaje > 0";
                }

                var tipoImpObj = await cmdTipoImp.ExecuteScalarAsync();
                if (tipoImpObj != null && tipoImpObj != DBNull.Value)
                {
                    tipoImpuestoVal = Convert.ToInt32(tipoImpObj);
                }

                // Obtendremos las cuentas por defecto más adelante para las 3 monedas

                // Insertar suplidor usando los mismos campos que el proyecto web/cxp/api
                using var cmdInsertSuplidor = connection.CreateCommand();
                cmdInsertSuplidor.CommandText = @"
                    INSERT INTO cxpSuplidores (
                        Nombre, RNC, Estatus, MostrarEnCXP, 
                        DiasCredito, PedirNCF, TipoImpuesto, 
                        FechaIngreso, TipoSuplidor, idMoneda, 
                        UidcxpSuplidores, idTipoIdentificacion, 
                        Direccion, Ciudad, Provincia, Pais
                    ) 
                    OUTPUT INSERTED.IdSuplidor
                    VALUES (
                        @Nombre, @RNC, 1, 1, 
                        0, 'S', @TipoImpuesto, 
                        @FechaIngreso, @TipoSuplidor, @idMoneda, 
                        NEWID(), '1', 
                        @Direccion, @Ciudad, @Provincia, @Pais
                    )";
                
                cmdInsertSuplidor.Parameters.AddWithValue("@Nombre", nuevoNombreSuplidor);
                cmdInsertSuplidor.Parameters.AddWithValue("@RNC", dto.RncSuplidor);
                cmdInsertSuplidor.Parameters.AddWithValue("@FechaIngreso", DateTime.UtcNow);
                cmdInsertSuplidor.Parameters.AddWithValue("@TipoSuplidor", tipoSuplidorVal);
                cmdInsertSuplidor.Parameters.AddWithValue("@TipoImpuesto", tipoImpuestoVal);
                cmdInsertSuplidor.Parameters.AddWithValue("@idMoneda", finalIdMoneda);
                cmdInsertSuplidor.Parameters.AddWithValue("@Direccion", string.IsNullOrWhiteSpace(dto.Direccion) ? DBNull.Value : dto.Direccion);
                cmdInsertSuplidor.Parameters.AddWithValue("@Ciudad", string.IsNullOrWhiteSpace(dto.Ciudad) ? DBNull.Value : dto.Ciudad);
                cmdInsertSuplidor.Parameters.AddWithValue("@Provincia", string.IsNullOrWhiteSpace(dto.Provincia) ? DBNull.Value : dto.Provincia);
                cmdInsertSuplidor.Parameters.AddWithValue("@Pais", string.IsNullOrWhiteSpace(dto.Pais) ? DBNull.Value : dto.Pais);

                var newIdObj = await cmdInsertSuplidor.ExecuteScalarAsync();
                
                idSuplidor = Convert.ToInt32(newIdObj);
                nombreSuplidor = nuevoNombreSuplidor;
                rncSuplidor = dto.RncSuplidor;
                tipoIdentificacion = "1";

                // Guardar la cuenta del suplidor para TODAS las monedas configuradas en la BD
                var monedas = new List<int>();
                using (var cmdMonedas = connection.CreateCommand())
                {
                    cmdMonedas.CommandText = "SELECT idMoneda FROM Moneda";
                    using (var reader = await cmdMonedas.ExecuteReaderAsync())
                    {
                        while (await reader.ReadAsync())
                        {
                            monedas.Add(reader.GetInt32(0));
                        }
                    }
                }

                foreach (int mon in monedas)
                {
                    string clavePasivo = mon switch { 2 => "ctacxpdolar", 3 => "ctacxpeuro", _ => "ctacxprd" };
                    string claveGasto = mon switch { 2 => "ctagastodolar", 3 => "ctagastoeuro", _ => "ctagastord" };

                    // Buscar Pasivo
                    using var cmdCtaPasivo = connection.CreateCommand();
                    cmdCtaPasivo.CommandText = "SELECT TOP 1 valor FROM Defaults WHERE Clave = @Clave";
                    cmdCtaPasivo.Parameters.AddWithValue("@Clave", clavePasivo);
                    var pasivoObj = await cmdCtaPasivo.ExecuteScalarAsync();
                    string idPasivo = pasivoObj?.ToString() ?? "";

                    // Buscar Gasto
                    using var cmdCtaGasto = connection.CreateCommand();
                    cmdCtaGasto.CommandText = "SELECT TOP 1 valor FROM Defaults WHERE Clave = @Clave";
                    cmdCtaGasto.Parameters.AddWithValue("@Clave", claveGasto);
                    var gastoObj = await cmdCtaGasto.ExecuteScalarAsync();
                    string idGasto = gastoObj?.ToString() ?? "";

                    // Si al menos hay pasivo, insertamos el registro
                    if (!string.IsNullOrEmpty(idPasivo))
                    {
                        using var cmdInsCta = connection.CreateCommand();
                        cmdInsCta.CommandText = "INSERT INTO cxpSuplidorCuenta (idSuplidor, idMoneda, idcuenta, idcuentaGasto) VALUES (@IdSup, @IdMon, @IdCta, @IdGasto)";
                        cmdInsCta.Parameters.AddWithValue("@IdSup", idSuplidor);
                        cmdInsCta.Parameters.AddWithValue("@IdMon", mon);
                        cmdInsCta.Parameters.AddWithValue("@IdCta", idPasivo);
                        cmdInsCta.Parameters.AddWithValue("@IdGasto", idGasto);
                        await cmdInsCta.ExecuteNonQueryAsync();
                    }
                }
            }

            // 3.5 Duplicate Check
            if (!string.IsNullOrEmpty(dto.Ncf))
            {
                using var cmdDup = connection.CreateCommand();
                cmdDup.CommandText = $"SELECT TOP 1 1 FROM cxpDocumentos WHERE idSuplidor = @CheckIdSup AND CompFiscal = @CheckNCF AND Status <> 'C'";
                cmdDup.Parameters.AddWithValue("@CheckIdSup", idSuplidor);
                cmdDup.Parameters.AddWithValue("@CheckNCF", dto.Ncf);

                var exists = await cmdDup.ExecuteScalarAsync();
                if (exists != null && exists != DBNull.Value)
                {
                    return ResultadoOperacion.Fallido("El Comprobante Fiscal (NCF) ya fue registrado para este suplidor.");
                }
            }

            // 4. Transactional Block for Defaults and Insert
            using var transaction = connection.BeginTransaction();
            try
            {
                // 4.1 Defaults Injection
                using var cmdDefaults = connection.CreateCommand();
                cmdDefaults.Transaction = transaction;
                cmdDefaults.CommandText = "SELECT Clave, Valor FROM Defaults WHERE Clave IN ('ClaseGasto', 'FormaPago', 'ctacxprd', 'ctacxpdolar', 'ctacxpeuro', 'CTAITBIS', 'CUENTA_PROPINA')";
                
                string idClaseGasto = "01"; // Fallback
                int idPagoForma = 1; // Fallback
                string cuentaPorPagarPorDefecto = "2000201"; // Fallback revision account
                string cuentaItbis = "";
                string cuentaPropina = "";

                using (var reader = await cmdDefaults.ExecuteReaderAsync())
                {
                    while (await reader.ReadAsync())
                    {
                        var clave = reader["Clave"]?.ToString();
                        var valor = reader["Valor"]?.ToString();

                        if (clave == "ClaseGasto" && !string.IsNullOrEmpty(valor)) idClaseGasto = valor;
                        if (clave == "FormaPago" && int.TryParse(valor, out int formaPagoVal)) idPagoForma = formaPagoVal;
                        
                        if (finalIdMoneda == 1 && clave == "ctacxprd" && !string.IsNullOrEmpty(valor)) cuentaPorPagarPorDefecto = valor;
                        if (finalIdMoneda == 2 && clave == "ctacxpdolar" && !string.IsNullOrEmpty(valor)) cuentaPorPagarPorDefecto = valor;
                        if (finalIdMoneda == 3 && clave == "ctacxpeuro" && !string.IsNullOrEmpty(valor)) cuentaPorPagarPorDefecto = valor;

                        if (clave == "CTAITBIS" && !string.IsNullOrEmpty(valor)) cuentaItbis = valor;
                        if (clave == "CUENTA_PROPINA" && !string.IsNullOrEmpty(valor)) cuentaPropina = valor;
                    }
                }

                // 4.2 Supplier Accounts
                using var cmdSupCta = connection.CreateCommand();
                cmdSupCta.Transaction = transaction;
                cmdSupCta.CommandText = "SELECT TOP 1 idcuenta, idcuentaGasto FROM cxpSuplidorCuenta WHERE idSuplidor = @IdSuplidor AND idMoneda = @IdMoneda";
                cmdSupCta.Parameters.AddWithValue("@IdSuplidor", idSuplidor);
                cmdSupCta.Parameters.AddWithValue("@IdMoneda", finalIdMoneda);
                
                string idCuentaPasivo = cuentaPorPagarPorDefecto;
                string idCuentaGasto = "";

                using (var readerCta = await cmdSupCta.ExecuteReaderAsync())
                {
                    if (await readerCta.ReadAsync())
                    {
                        if (!readerCta.IsDBNull(0)) idCuentaPasivo = readerCta.GetString(0);
                        if (!readerCta.IsDBNull(1)) idCuentaGasto = readerCta.GetString(1);
                    }
                }

                // 4.3 Tax Definition (Impuestos)
                using var cmdTaxes = connection.CreateCommand();
                cmdTaxes.Transaction = transaction;
                cmdTaxes.CommandText = "SELECT TOP 1 TipoImpuesto, idCuenta FROM ocTiposImpuestos WHERE AutoIncluir = 1";
                int? tipoImpuestoId = null;
                string cuentaImpuesto = cuentaItbis; // fallback to Defaults

                using (var readerTaxes = await cmdTaxes.ExecuteReaderAsync())
                {
                    if (await readerTaxes.ReadAsync())
                    {
                        if (!readerTaxes.IsDBNull(0)) tipoImpuestoId = Convert.ToInt32(readerTaxes["TipoImpuesto"]);
                        if (!readerTaxes.IsDBNull(1) && !string.IsNullOrEmpty(readerTaxes["idCuenta"].ToString())) 
                            cuentaImpuesto = readerTaxes["idCuenta"].ToString()!;
                    }
                }

                // 4.3.5 Obtener Tasa de Cambio
                decimal tasaCambio = 1m;
                if (finalIdMoneda != 1)
                {
                    using var cmdTasa = connection.CreateCommand();
                    cmdTasa.Transaction = transaction;
                    cmdTasa.CommandText = "SELECT TOP 1 Tasa FROM Tasa WHERE idMoneda = @IdMon AND Fecha <= @FechaFact ORDER BY Fecha DESC";
                    cmdTasa.Parameters.AddWithValue("@IdMon", finalIdMoneda);
                    cmdTasa.Parameters.AddWithValue("@FechaFact", dto.FechaFactura.Date);
                    var tasaObj = await cmdTasa.ExecuteScalarAsync();
                    if (tasaObj != null && tasaObj != DBNull.Value)
                    {
                        tasaCambio = Convert.ToDecimal(tasaObj);
                    }
                }

                // 4.4 Invoice Insertion
                using var cmdInsert = connection.CreateCommand();
                cmdInsert.Transaction = transaction;
                cmdInsert.CommandText = @"
                    INSERT INTO cxpDocumentos (
                        idTrans, Fecha, idSuplidor, Referencia, Valor, 
                        MontoImpuestos, MontoDescuento, MontoRetenciones, Concepto, 
                        idMoneda, CodifManual, Status, FechaStatus, idCuenta, 
                        TipoDocOrigen, DocOrigen, Dias, MostrarenCxP, BienesServicio,
                        NotaAdicional, idAuxiliar, CompFiscal, GUIDDocumento, 
                        idTipoIdentificacion, idClaseGasto, Tasa, TipoAbono, 
                        RNC, Nombre, Vencimiento, FechaEmision, TipoGasto,
                        idPagoForma, montoFacturadoBienes, montoFacturadoServicios, 
                        MontoItbisCosto, MontoIsc, OtrosImpuestos, PropinaLegal,
                        idPartida, OrdenCompra, CuentaDestino, BancoDestino, Usuario
                    ) 
                    OUTPUT INSERTED.idDocumento
                    VALUES (
                        @IdTrans, @Fecha, @IdSuplidor, @Referencia, @Valor, 
                        @MontoImpuestos, 0, 0, @Concepto, 
                        @IdMoneda, 1, 'A', @FechaStatus, @IdCuenta, 
                        '', 0, 0, 0, @BienesServicio,
                        '', '', @CompFiscal, @GUIDDocumento, 
                        @IdTipoIdentificacion, @IdClaseGasto, @Tasa, '1', 
                        @RNC, @Nombre, @Vencimiento, @FechaEmision, 'COSTO',
                        @IdPagoForma, @MontoFBienes, @MontoFServicios, 
                        @MontoItbisCosto, @MontoIsc, @OtrosImpuestos, @Propina,
                        '', '', '', '', @Usuario
                    )";

                var addParam = (string name, object? value) => {
                    var p = cmdInsert.CreateParameter();
                    p.ParameterName = name;
                    p.Value = value ?? DBNull.Value;
                    cmdInsert.Parameters.Add(p);
                };

                addParam("@IdTrans", 1); // Factura de Compra
                addParam("@Fecha", dto.FechaFactura.Date);
                addParam("@FechaStatus", DateTime.Now);
                addParam("@IdSuplidor", idSuplidor);
                addParam("@Referencia", dto.Ncf); // Uso NCF como referencia si no hay otra
                addParam("@Valor", dto.Subtotal); // EN EL ERP VALOR ES EL SUBTOTAL
                addParam("@MontoImpuestos", dto.Itbis);
                addParam("@Concepto", $"Factura externa {dto.Ncf}");
                addParam("@CompFiscal", dto.Ncf);
                addParam("@GUIDDocumento", Guid.NewGuid());
                addParam("@IdMoneda", finalIdMoneda);
                addParam("@Tasa", tasaCambio);
                addParam("@IdClaseGasto", idClaseGasto);
                addParam("@IdCuenta", idCuentaPasivo);
                addParam("@IdTipoIdentificacion", tipoIdentificacion);
                addParam("@RNC", dto.RncSuplidor);
                addParam("@Nombre", nombreSuplidor);
                addParam("@Vencimiento", dto.FechaFactura.Date);
                addParam("@FechaEmision", dto.FechaFactura.Date);
                addParam("@IdPagoForma", idPagoForma);
                addParam("@BienesServicio", dto.EsServicio ? 2 : 1);
                addParam("@MontoFBienes", dto.EsServicio ? 0m : dto.Subtotal);
                addParam("@MontoFServicios", dto.EsServicio ? dto.Subtotal : 0m);
                addParam("@Propina", dto.Propina);
                addParam("@MontoIsc", dto.Isc);
                addParam("@OtrosImpuestos", dto.OtrosImpuestos);
                addParam("@MontoItbisCosto", dto.ItbisAlCosto);
                addParam("@Usuario", "API_EXTERNA");

                var insertedIdObj = await cmdInsert.ExecuteScalarAsync();
                int insertedId = Convert.ToInt32(insertedIdObj);

                // 4.5 Guardar relacion de impuesto si existe
                if (dto.Itbis > 0 && tipoImpuestoId.HasValue)
                {
                    using var cmdImps = connection.CreateCommand();
                    cmdImps.Transaction = transaction;
                    cmdImps.CommandText = "INSERT INTO cxpDocImpuestos (idDocumento, TipoImpuesto) VALUES (@idDocumento, @TipoImpuesto)";
                    cmdImps.Parameters.AddWithValue("@idDocumento", insertedId);
                    cmdImps.Parameters.AddWithValue("@TipoImpuesto", tipoImpuestoId.Value);
                    await cmdImps.ExecuteNonQueryAsync();
                }

                // 4.6 Codificacion Contable
                async Task InsertarCuenta(string cta, short dbcr, decimal val, bool esItbis = false)
                {
                    if (string.IsNullOrEmpty(cta) || val <= 0) return;

                    decimal valBase = val;
                    decimal valPrima = 0m;
                    string ctaPrima = cta;

                    if (finalIdMoneda != 1)
                    {
                        if (esItbis)
                        {
                            // ITBIS se asienta directamente convertido
                            valBase = Math.Round(val * tasaCambio, 2);
                        }
                        else
                        {
                            valPrima = Math.Round(val * (tasaCambio - 1m), 2);
                            
                            // Buscar cuenta prima
                            using var cmdCtaPrima = connection.CreateCommand();
                            cmdCtaPrima.Transaction = transaction;
                            cmdCtaPrima.CommandText = "SELECT TOP 1 idCuentaPrima FROM cgCuentaPrima WHERE idCuenta = @IdCta AND idMoneda = @IdMon";
                            cmdCtaPrima.Parameters.AddWithValue("@IdCta", cta);
                            cmdCtaPrima.Parameters.AddWithValue("@IdMon", finalIdMoneda);
                            var objPrima = await cmdCtaPrima.ExecuteScalarAsync();
                            if (objPrima != null && objPrima != DBNull.Value)
                            {
                                ctaPrima = objPrima.ToString()!;
                            }
                        }
                    }

                    // Insertar Base (Original o ITBIS convertido)
                    using var cmdCta1 = connection.CreateCommand();
                    cmdCta1.Transaction = transaction;
                    cmdCta1.CommandText = "cxpGuardarCtasDoc;1";
                    cmdCta1.CommandType = System.Data.CommandType.StoredProcedure;
                    cmdCta1.Parameters.AddWithValue("@IdDocumento", insertedId);
                    cmdCta1.Parameters.AddWithValue("@Cta", cta);
                    cmdCta1.Parameters.AddWithValue("@Aux", DBNull.Value);
                    cmdCta1.Parameters.AddWithValue("@dbcr", dbcr);
                    cmdCta1.Parameters.AddWithValue("@Valor", valBase);
                    cmdCta1.Parameters.AddWithValue("@Automatica", true);
                    cmdCta1.Parameters.AddWithValue("@idCentroCosto", DBNull.Value);
                    cmdCta1.Parameters.AddWithValue("@CentroCosto", DBNull.Value);
                    cmdCta1.Parameters.AddWithValue("@idPartida", DBNull.Value);
                    await cmdCta1.ExecuteNonQueryAsync();

                    // Insertar Prima si aplica
                    if (valPrima > 0)
                    {
                        using var cmdCta2 = connection.CreateCommand();
                        cmdCta2.Transaction = transaction;
                        cmdCta2.CommandText = "cxpGuardarCtasDoc;1";
                        cmdCta2.CommandType = System.Data.CommandType.StoredProcedure;
                        cmdCta2.Parameters.AddWithValue("@IdDocumento", insertedId);
                        cmdCta2.Parameters.AddWithValue("@Cta", ctaPrima);
                        cmdCta2.Parameters.AddWithValue("@Aux", DBNull.Value);
                        cmdCta2.Parameters.AddWithValue("@dbcr", dbcr);
                        cmdCta2.Parameters.AddWithValue("@Valor", valPrima);
                        cmdCta2.Parameters.AddWithValue("@Automatica", true);
                        cmdCta2.Parameters.AddWithValue("@idCentroCosto", DBNull.Value);
                        cmdCta2.Parameters.AddWithValue("@CentroCosto", DBNull.Value);
                        cmdCta2.Parameters.AddWithValue("@idPartida", DBNull.Value);
                        await cmdCta2.ExecuteNonQueryAsync();
                    }
                }

                decimal totalCalculado = dto.Subtotal + dto.Itbis + dto.Propina + dto.Isc + dto.OtrosImpuestos;

                // ITBIS (Debito) - Se envía esItbis = true para conversión directa
                if (dto.Itbis > 0) await InsertarCuenta(cuentaImpuesto, 1, dto.Itbis, true);
                // Propina (Debito)
                if (dto.Propina > 0) await InsertarCuenta(cuentaPropina, 1, dto.Propina);
                // Gasto Subtotal (Debito)
                if (dto.Subtotal > 0) await InsertarCuenta(idCuentaGasto, 1, dto.Subtotal);
                // Pasivo Total (Credito)
                if (totalCalculado > 0) await InsertarCuenta(idCuentaPasivo, 2, totalCalculado);

                transaction.Commit();
                
                return ResultadoOperacion.Exitoso("Factura integrada correctamente con distribución contable.", new { IdDocumento = insertedId });
            }
            catch (Exception ex)
            {
                transaction.Rollback();
                _logger.LogError(ex, "Error insertando factura externa para RNC {RncSuplidor}", dto.RncSuplidor);
                return ResultadoOperacion.Fallido($"Error interno de base de datos: {ex.Message}");
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error procesando factura externa");
            return ResultadoOperacion.Fallido($"Error procesando factura: {ex.Message}");
        }
    }
}
