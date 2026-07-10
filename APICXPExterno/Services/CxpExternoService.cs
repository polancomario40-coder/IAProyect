using CxpApi.Data;
using CxpApi.Models;
using Microsoft.Data.SqlClient;

namespace CxpApi.Services;

public class CxpExternoService : ICxpExternoService
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<CxpExternoService> _logger;

    public CxpExternoService(IServiceProvider serviceProvider, ILogger<CxpExternoService> logger)
    {
        _serviceProvider = serviceProvider;
        _logger = logger;
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

                var servidor = empresa.Servidor?.Trim() ?? "";
                if (servidor == "10.0.0.6" || servidor == "127.0.0.6" || servidor == "127.0.0.1" || servidor.ToLower() == "localhost")
                {
                    servidor = "localhost";
                }

                var builder = new SqlConnectionStringBuilder
                {
                    DataSource = servidor,
                    InitialCatalog = empresa.BaseDatos?.Trim() ?? "",
                    TrustServerCertificate = true,
                    Encrypt = false
                };

                if (empresa.Trusted == true)
                {
                    builder.IntegratedSecurity = true;
                }
                else
                {
                    builder.UserID = empresa.UserId?.Trim() ?? "";
                    // Assuming Encriptada logic is skipped or trivial here as requested, or taking it as is:
                    builder.Password = empresa.UserPwd?.Trim() ?? ""; // Note: decryption logic should match ErpConnectionProvider if needed
                }

                connectionString = builder.ConnectionString;
            }

            using var connection = new SqlConnection(connectionString);
            await connection.OpenAsync();

            // 3. Supplier Validation
            using var cmdCheckSuplidor = connection.CreateCommand();
            cmdCheckSuplidor.CommandText = "SELECT TOP 1 IdSuplidor, Nombre, RNC, idTipoIdentificacion FROM cxpSuplidores WHERE RNC = @rnc AND Estatus = 1";
            cmdCheckSuplidor.Parameters.AddWithValue("@rnc", dto.RncSuplidor);
            
            int idSuplidor = 0;
            string nombreSuplidor = "";
            string rncSuplidor = dto.RncSuplidor;
            string tipoIdentificacion = "1"; // Default

            using (var reader = await cmdCheckSuplidor.ExecuteReaderAsync())
            {
                if (await reader.ReadAsync())
                {
                    idSuplidor = Convert.ToInt32(reader["IdSuplidor"]);
                    nombreSuplidor = reader["Nombre"]?.ToString() ?? "";
                    rncSuplidor = reader["RNC"]?.ToString() ?? dto.RncSuplidor;
                    tipoIdentificacion = reader["idTipoIdentificacion"]?.ToString() ?? "1";
                }
                else
                {
                    return ResultadoOperacion.Fallido($"El suplidor con RNC '{dto.RncSuplidor}' no existe o está inactivo. Debe ser creado primero.");
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
                cmdDefaults.CommandText = "SELECT Clave, Valor FROM Defaults WHERE Clave IN ('ClaseGasto', 'FormaPago', 'supl_idcuenta', 'CUENTA_ITBIS', 'CUENTA_PROPINA')";
                
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
                        if (clave == "supl_idcuenta" && !string.IsNullOrEmpty(valor)) cuentaPorPagarPorDefecto = valor;
                        if (clave == "CUENTA_ITBIS" && !string.IsNullOrEmpty(valor)) cuentaItbis = valor;
                        if (clave == "CUENTA_PROPINA" && !string.IsNullOrEmpty(valor)) cuentaPropina = valor;
                    }
                }

                // 4.2 Supplier Accounts
                using var cmdSupCta = connection.CreateCommand();
                cmdSupCta.Transaction = transaction;
                cmdSupCta.CommandText = "SELECT TOP 1 idcuenta, idcuentaGasto FROM cxpSuplidorCuenta WHERE idSuplidor = @IdSuplidor";
                cmdSupCta.Parameters.AddWithValue("@IdSuplidor", idSuplidor);
                
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
                        1, 1, 'A', @FechaStatus, @IdCuenta, 
                        '', 0, 0, 0, @BienesServicio,
                        '', '', @CompFiscal, @GUIDDocumento, 
                        @IdTipoIdentificacion, @IdClaseGasto, 1, '1', 
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
                async Task InsertarCuenta(string cta, short dbcr, decimal val)
                {
                    if (string.IsNullOrEmpty(cta) || val <= 0) return;
                    using var cmdCta = connection.CreateCommand();
                    cmdCta.Transaction = transaction;
                    cmdCta.CommandText = "cxpGuardarCtasDoc;1";
                    cmdCta.CommandType = System.Data.CommandType.StoredProcedure;
                    cmdCta.Parameters.AddWithValue("@IdDocumento", insertedId);
                    cmdCta.Parameters.AddWithValue("@Cta", cta);
                    cmdCta.Parameters.AddWithValue("@Aux", DBNull.Value);
                    cmdCta.Parameters.AddWithValue("@dbcr", dbcr);
                    cmdCta.Parameters.AddWithValue("@Valor", val);
                    cmdCta.Parameters.AddWithValue("@Automatica", true);
                    cmdCta.Parameters.AddWithValue("@idCentroCosto", DBNull.Value);
                    cmdCta.Parameters.AddWithValue("@CentroCosto", DBNull.Value);
                    cmdCta.Parameters.AddWithValue("@idPartida", DBNull.Value);
                    await cmdCta.ExecuteNonQueryAsync();
                }

                decimal totalCalculado = dto.Subtotal + dto.Itbis + dto.Propina + dto.Isc + dto.OtrosImpuestos;

                // ITBIS (Debito)
                if (dto.Itbis > 0) await InsertarCuenta(cuentaImpuesto, 1, dto.Itbis);
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
