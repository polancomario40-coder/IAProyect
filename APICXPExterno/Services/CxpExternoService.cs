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
            if (dto.Subtotal + dto.Itbis != dto.Total)
            {
                return ResultadoOperacion.Fallido($"Error matemático: Subtotal ({dto.Subtotal}) + ITBIS ({dto.Itbis}) no coincide con el Total ({dto.Total}).");
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
            cmdCheckSuplidor.CommandText = "SELECT TOP 1 IdSuplidor, Nombre, RNC, idTipoIdentificacion FROM cxpSuplidores WHERE RNC = @rnc AND Status <> 'C'";
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

            // 4. Transactional Block for Defaults and Insert
            using var transaction = connection.BeginTransaction();
            try
            {
                // 4.1 Defaults Injection
                using var cmdDefaults = connection.CreateCommand();
                cmdDefaults.Transaction = transaction;
                cmdDefaults.CommandText = "SELECT Clave, Valor FROM Defaults WHERE Categoria = 'CXPAPP' AND Clave IN ('ClaseGasto', 'FormaPago', 'supl_idcuenta')";
                
                string idClaseGasto = "01"; // Fallback
                int idPagoForma = 1; // Fallback
                string idCuenta = "2000201"; // Fallback revision account

                using (var reader = await cmdDefaults.ExecuteReaderAsync())
                {
                    while (await reader.ReadAsync())
                    {
                        var clave = reader["Clave"]?.ToString();
                        var valor = reader["Valor"]?.ToString();

                        if (clave == "ClaseGasto" && !string.IsNullOrEmpty(valor)) idClaseGasto = valor;
                        if (clave == "FormaPago" && int.TryParse(valor, out int formaPagoVal)) idPagoForma = formaPagoVal;
                        if (clave == "supl_idcuenta" && !string.IsNullOrEmpty(valor)) idCuenta = valor;
                    }
                }

                // 4.2 Invoice Insertion
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
                        1, 0, 'A', @FechaStatus, @IdCuenta, 
                        '', 0, 0, 0, 1,
                        '', '', @CompFiscal, @GUIDDocumento, 
                        @IdTipoIdentificacion, @IdClaseGasto, 1, '1', 
                        @RNC, @Nombre, @Vencimiento, @FechaEmision, 'COSTO',
                        @IdPagoForma, @MontoFBienes, @MontoFServicios, 
                        0, 0, 0, 0,
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
                addParam("@Valor", dto.Total);
                addParam("@MontoImpuestos", dto.Itbis);
                addParam("@Concepto", $"Factura externa {dto.Ncf}");
                addParam("@CompFiscal", dto.Ncf);
                addParam("@GUIDDocumento", Guid.NewGuid());
                addParam("@IdClaseGasto", idClaseGasto);
                addParam("@IdCuenta", idCuenta);
                addParam("@IdTipoIdentificacion", tipoIdentificacion);
                addParam("@RNC", rncSuplidor);
                addParam("@Nombre", nombreSuplidor);
                addParam("@Vencimiento", dto.FechaFactura.Date);
                addParam("@FechaEmision", dto.FechaFactura.Date);
                addParam("@IdPagoForma", idPagoForma);
                addParam("@MontoFBienes", dto.Subtotal); // Assuming goods
                addParam("@MontoFServicios", 0m);
                addParam("@Usuario", "API_EXTERNA");

                var insertedId = await cmdInsert.ExecuteScalarAsync();

                transaction.Commit();
                
                return ResultadoOperacion.Exitoso("Factura integrada correctamente.", new { IdDocumento = Convert.ToInt32(insertedId) });
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
