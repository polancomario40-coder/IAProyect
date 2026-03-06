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
        var idUsuario = User.FindFirst("idSegUserGrp")?.Value ?? "UNKNOWN";

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
                    1, 0, 'A', @Fecha, '2000201', 
                    '', 0, 0, 1, 1,
                    '', '', @CompFiscal, @GUIDDocumento, 
                    '02', @IdClasegasto, 1, '1', 
                    @RNC, @Nombre, @Vencimiento, @FechaEmision, 'COSTO',
                    4, 0, @Valor, 
                    0, 0, 0, 0,
                    '', '', '', ''
                )";

            addParam("@Fecha", fechaActual);
            addParam("@IdSuplidor", request.IdSuplidor);
            addParam("@Referencia", refDefinitiva);
            addParam("@Valor", request.Valor);
            addParam("@MontoImpuestos", request.MontoImpuestos);
            addParam("@Concepto", conceptoDefinitivo);
            addParam("@CompFiscal", ncfDefinitivo);
            addParam("@GUIDDocumento", guidDoc);
            addParam("@IdClasegasto", string.IsNullOrEmpty(request.IdClasegasto) ? "1" : request.IdClasegasto);
            addParam("@RNC", rncDefinitivo);
            addParam("@Nombre", nombreDefinitivo);
            addParam("@Vencimiento", request.Vencimiento.HasValue ? request.Vencimiento.Value : fechaActual);
            addParam("@FechaEmision", request.FechaEmision);

            var resultId = await command.ExecuteScalarAsync();
            var finalId = Convert.ToInt32(resultId);

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
