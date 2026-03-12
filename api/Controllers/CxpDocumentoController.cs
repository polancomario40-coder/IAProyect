using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using CxpApi.Data;
using CxpApi.Models;
using System.Security.Claims;

namespace CxpApi.Controllers;

public class FacturaRequest
{
    public int IdSuplidor { get; set; }
    public DateTime FechaEmision { get; set; }
    public DateTime? Vencimiento { get; set; }
    public string? Referencia { get; set; }
    public string? CompFiscal { get; set; }
    public string? Concepto { get; set; }
    public decimal Valor { get; set; }
    public decimal MontoImpuestos { get; set; }
    public decimal Total { get; set; }
    public string? RNC { get; set; }
    public string? Nombre { get; set; }
    public string? IdClasegasto { get; set; }
    public int IdMoneda { get; set; }
    public int IdPagoForma { get; set; }
    public bool EsServicio { get; set; }
    public string? FotoBase64 { get; set; }
}

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class CxpDocumentoController : ControllerBase
{
    private readonly AppDbContext _erpDb;

    public CxpDocumentoController(AppDbContext erpDb)
    {
        _erpDb = erpDb;
    }

    [HttpPost]
    public async Task<IActionResult> CreateFactura([FromBody] FacturaRequest request)
    {
        var idUsuario = User.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value ?? "UNKNOWN";

        var nuevoDoc = new CxpDocumento
        {
            IdSuplidor = request.IdSuplidor,
            FechaEmision = request.FechaEmision,
            Vencimiento = request.Vencimiento,
            Referencia = request.Referencia,
            CompFiscal = request.CompFiscal,
            Concepto = request.Concepto,
            Valor = request.Valor,
            MontoImpuestos = request.MontoImpuestos,
            RNC = request.RNC,
            Nombre = request.Nombre,
            Usuario = idUsuario,
            // Campos auto-completados por el backend (Definidos en el Modelo per defecto)
            // GUIDDocumento = Guid.NewGuid(),
            // Fecha = DateTime.UtcNow,
            // FechaRegistro = DateTime.UtcNow,
            // Status = "A",
            // FechaStatus = DateTime.UtcNow,
            // Cancelado = false,
            // PendValidacion = true,
            // PendEnvioEcf = true
        };

        // Generar Guids y Fechas como lo espera Delphi
        var guidDoc = Guid.NewGuid();
        var fechaActual = DateTime.UtcNow;
        var rncDefinitivo = string.IsNullOrEmpty(request.RNC) ? "" : request.RNC;
        var nombreDefinitivo = string.IsNullOrEmpty(request.Nombre) ? "" : request.Nombre;
        var refDefinitiva = string.IsNullOrEmpty(request.Referencia) ? "" : request.Referencia;
        var ncfDefinitivo = string.IsNullOrEmpty(request.CompFiscal) ? "" : request.CompFiscal;
        var conceptoDefinitivo = string.IsNullOrEmpty(request.Concepto) ? "" : request.Concepto;

        try
        {
            await _erpDb.Database.OpenConnectionAsync();
            var connection = _erpDb.Database.GetDbConnection();

            using var transaction = connection.BeginTransaction();
            var command = connection.CreateCommand();
            command.Transaction = transaction;

            var addParam = (string name, object? value) => {
                var p = command.CreateParameter();
                p.ParameterName = name;
                p.Value = value ?? DBNull.Value;
                command.Parameters.Add(p);
            };

            // 1. DUPLICATE CHECK
            command.CommandText = "SELECT 1 FROM cxpDocumentos WHERE idSuplidor = @CheckIdSup AND Referencia = @CheckRef";
            addParam("@CheckIdSup", request.IdSuplidor);
            addParam("@CheckRef", refDefinitiva);

            var exists = await command.ExecuteScalarAsync();
            if (exists != null && exists != DBNull.Value)
            {
                return Conflict("Este Comprobante Fiscal ya fue registrado para este suplidor");
            }

            // 2. INSERT FACTURA
            command.CommandText = @"
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
                    idPartida, OrdenCompra, CuentaDestino, BancoDestino
                ) 
                OUTPUT INSERTED.idDocumento
                VALUES (
                    13, @Fecha, @IdSuplidor, @Referencia, @Valor, 
                    @MontoImpuestos, 0, 0, @Concepto, 
                    @IdMoneda, 0, 'A', @Fecha, '2000201', 
                    '', 0, 0, 0, 1,
                    '', '', @CompFiscal, @GUIDDocumento, 
                    '02', @IdClasegasto, 1, '1', 
                    @RNC, @Nombre, @Vencimiento, @FechaEmision, 'COSTO',
                    @IdPagoForma, @MontoFBienes, @MontoFServicios, 
                    0, 0, 0, 0,
                    '', '', '', ''
                )";

            addParam("@Fecha", fechaActual);
            addParam("@IdSuplidor", request.IdSuplidor);
            addParam("@Referencia", refDefinitiva);
            addParam("@Valor", request.Valor);
            addParam("@MontoImpuestos", request.MontoImpuestos);
            addParam("@Concepto", conceptoDefinitivo);
            addParam("@IdMoneda", request.IdMoneda);
            addParam("@CompFiscal", ncfDefinitivo);
            addParam("@GUIDDocumento", guidDoc);
            addParam("@IdClasegasto", string.IsNullOrEmpty(request.IdClasegasto) ? "1" : request.IdClasegasto);
            addParam("@RNC", rncDefinitivo);
            addParam("@Nombre", nombreDefinitivo);
            addParam("@Vencimiento", request.Vencimiento.HasValue ? request.Vencimiento.Value : fechaActual);
            addParam("@FechaEmision", request.FechaEmision);
            addParam("@IdPagoForma", request.IdPagoForma);
            
            // Logica Bienes/Servicios Distribuido
            if (request.EsServicio)
            {
                addParam("@MontoFBienes", 0m);
                addParam("@MontoFServicios", request.Valor);
            }
            else
            {
                addParam("@MontoFBienes", request.Valor);
                addParam("@MontoFServicios", 0m);
            }

            var resultId = await command.ExecuteScalarAsync();
            var finalId = Convert.ToInt32(resultId);

            // 3. INSERT IMAGEN (Si existe)
            if (!string.IsNullOrEmpty(request.FotoBase64))
            {
                // Limpiar prefijo data:image/xxx;base64, si el frontend lo envió
                var base64Data = request.FotoBase64;
                if (base64Data.Contains(","))
                {
                    base64Data = base64Data.Substring(base64Data.IndexOf(",") + 1);
                }

                byte[] imageBytes = Convert.FromBase64String(base64Data);

                var imgCommand = connection.CreateCommand();
                imgCommand.Transaction = transaction;
                imgCommand.CommandText = @"
                    INSERT INTO ImgImagen (
                        idImagen, idDocumento, imagen, Fecha, TipoDoc, esPDF
                    ) VALUES (
                        @IdImagen, @IdDocumento, @Imagen, @FechaImg, 'FacturaCXP', 0
                    )";

                var addImgParam = (string name, object? value) => {
                    var p = imgCommand.CreateParameter();
                    p.ParameterName = name;
                    p.Value = value ?? DBNull.Value;
                    imgCommand.Parameters.Add(p);
                };

                addImgParam("@IdImagen", Guid.NewGuid());
                addImgParam("@IdDocumento", guidDoc);
                addImgParam("@Imagen", imageBytes);
                addImgParam("@FechaImg", DateTime.Now);

                await imgCommand.ExecuteNonQueryAsync();
            }

            transaction.Commit();

            return Ok(new 
            {
                success = true,
                mensaje = "Factura registrada exitosamente con SQL Directo.",
                idDocumento = finalId,
                guidDocumento = guidDoc,
                databaseDestino = connection.Database,
                serverDestino = connection.DataSource
            });
        }
        catch (Exception ex)
        {
            var msg = ex.InnerException?.Message ?? ex.Message;
            return BadRequest(new { mensaje = $"Error SQL directo al registrar: {msg}" });
        }
    }

    [HttpPost("escanear")]
    public async Task<IActionResult> EscanearFactura([FromBody] OcrRequest request)
    {
        if (string.IsNullOrEmpty(request.FotoBase64))
        {
            return BadRequest(new { success = false, mensaje = "No se recibió ninguna imagen." });
        }

        // Simular el tiempo lógico de envío al proveedor de IA, procesamiento y respuesta
        await Task.Delay(2500);

        // Generar data mística/realista de prueba
        var rnd = new Random();
        var numBienes = rnd.Next(1000, 5000) + (decimal)rnd.NextDouble();
        var ncfAleatorio = "B01" + rnd.Next(10000000, 99999999).ToString("D8"); // Ej: B0112345678
        var rncAleatorio = rnd.Next(100000000, 999999999).ToString();

        // Respuesta artificial
        var response = new OcrResponse
        {
            Success = true,
            Mensaje = "Extracción completada",
            RNC = rncAleatorio,
            NCF = ncfAleatorio,
            Fecha = DateTime.UtcNow.Date.AddDays(-rnd.Next(1, 30)), // Fecha aleatoria en el último mes
            TotalBienes = Math.Round(numBienes, 2),
            TotalServicios = 0.00m
        };

        return Ok(response);
    }

    [HttpGet("registradas")]
    public async Task<IActionResult> GetFacturasRegistradas([FromQuery] string? buscar)
    {
        var idUsuario = User.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        if (string.IsNullOrEmpty(idUsuario))
        {
            // Fallback for cases where it might not be securely mapped, though Authorize should catch it
            idUsuario = "UNKNOWN"; 
        }

        try
        {
            await _erpDb.Database.OpenConnectionAsync();
            var connection = _erpDb.Database.GetDbConnection();

            var command = connection.CreateCommand();
            
            string whereFilter = "";
            if (!string.IsNullOrWhiteSpace(buscar))
            {
                whereFilter = "WHERE d.Nombre LIKE '%' + @Buscar + '%' OR d.CompFiscal LIKE '%' + @Buscar + '%' OR d.RNC LIKE '%' + @Buscar + '%' OR d.Referencia LIKE '%' + @Buscar + '%'";
                var pSearch = command.CreateParameter();
                pSearch.ParameterName = "@Buscar";
                pSearch.Value = buscar.Trim();
                command.Parameters.Add(pSearch);
            }

            command.CommandText = $@"
                SELECT TOP 50
                    d.idDocumento,
                    d.GUIDDocumento,
                    d.FechaEmision,
                    d.CompFiscal,
                    d.Concepto,
                    (COALESCE(d.montoFacturadoBienes, 0) + COALESCE(d.montoFacturadoServicios, 0)) as Total,
                    d.RNC,
                    d.Nombre,
                    CASE WHEN i.idDocumento IS NOT NULL THEN 1 ELSE 0 END as TieneImagen
                FROM cxpDocumentos d
                LEFT JOIN ImgImagen i ON d.GUIDDocumento = i.idDocumento
                {whereFilter}
                ORDER BY d.Fecha DESC
            ";
            
            var param = command.CreateParameter();
            param.ParameterName = "@Usuario";
            param.Value = idUsuario;
            command.Parameters.Add(param);

            var facturas = new List<object>();

            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                {
                    facturas.Add(new
                    {
                        idDocumento = reader["idDocumento"],
                        guidDocumento = reader["GUIDDocumento"],
                        fechaEmision = reader["FechaEmision"],
                        compFiscal = reader["CompFiscal"]?.ToString(),
                        concepto = reader["Concepto"]?.ToString(),
                        total = reader["Total"],
                        rnc = reader["RNC"]?.ToString(),
                        nombre = reader["Nombre"]?.ToString(),
                        tieneImagen = Convert.ToBoolean(reader["TieneImagen"])
                    });
                }
            }

            return Ok(facturas);
        }
        catch (Exception ex)
        {
            return BadRequest(new { mensaje = "Error al obtener las facturas registradas.", detalle = ex.Message });
        }
    }

    [HttpGet("{guid}/imagen")]
    public async Task<IActionResult> GetImagenFactura(Guid guid)
    {
        try
        {
            await _erpDb.Database.OpenConnectionAsync();
            var connection = _erpDb.Database.GetDbConnection();

            var command = connection.CreateCommand();
            command.CommandText = "SELECT imagen FROM ImgImagen WHERE idDocumento = @IdDocumento";
            
            var param = command.CreateParameter();
            param.ParameterName = "@IdDocumento";
            param.Value = guid;
            command.Parameters.Add(param);

            var imageObj = await command.ExecuteScalarAsync();

            if (imageObj != null && imageObj != DBNull.Value)
            {
                byte[] imageBytes = (byte[])imageObj;
                string base64String = Convert.ToBase64String(imageBytes);
                return Ok(new { success = true, imagenBase64 = base64String });
            }

            return NotFound(new { success = false, mensaje = "Imagen no encontrada." });
        }
        catch (Exception ex)
        {
            return BadRequest(new { success = false, mensaje = "Error al obtener la imagen.", detalle = ex.Message });
        }
    }
    
    [HttpGet("tables")]
    [AllowAnonymous]
    public async Task<IActionResult> GetTables()
    {
        var tables = new List<string>();
        using (var command = _erpDb.Database.GetDbConnection().CreateCommand())
        {
            // Busca codigo fuente de triggers para cxpDocumentos
            command.CommandText = @"
                SELECT m.definition 
                FROM sys.triggers t 
                INNER JOIN sys.sql_modules m ON t.object_id = m.object_id 
                WHERE t.parent_id = OBJECT_ID('cxpDocumentos')";
            _erpDb.Database.OpenConnection();
            using (var result = await command.ExecuteReaderAsync())
            {
                while (await result.ReadAsync())
                {
                    tables.Add(result.GetString(0));
                }
            }
        }
        return Ok(tables);
    }

    [HttpGet("schema")]
    [AllowAnonymous]
    public async Task<IActionResult> GetSchema()
    {
        var schema = new List<object>();
        using (var command = _erpDb.Database.GetDbConnection().CreateCommand())
        {
            command.CommandText = "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'cxpDocumentos'";
            _erpDb.Database.OpenConnection();
            using (var result = await command.ExecuteReaderAsync())
            {
                while (await result.ReadAsync())
                {
                    schema.Add(new
                    {
                        Column = result.GetString(0),
                        Type = result.GetString(1)
                    });
                }
            }
        }
        return Ok(schema);
    }
}
