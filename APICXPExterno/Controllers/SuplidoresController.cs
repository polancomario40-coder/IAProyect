using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using CxpApi.Data;

namespace CxpApi.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize] // Protegido por JWT
public class SuplidoresController : ControllerBase
{
    private readonly AppDbContext _erpDb;

    public SuplidoresController(AppDbContext erpDb)
    {
        _erpDb = erpDb;
    }

    [HttpGet]
    public async Task<IActionResult> GetSuplidores()
    {
        // Se ejecuta utilizando la base de datos resuelta dinámicamente
        var suplidores = await _erpDb.CxpSuplidores
            .Where(s => (s.Estatus ?? false) == true && (s.MostrarEnCXP ?? false) == true)
            .Select(s => new
            {
                s.IdSuplidor,
                s.Nombre,
                s.RNC,
                s.Direccion,
                s.Telefono1,
                s.EMail,
                s.DiasCredito,
                s.LimiteCredito,
                s.TipoImpuesto,
                s.IdMoneda,
                PedirNCF = s.PedirNCF == "S",
                s.FormaPago,
                s.Grupo
            })
            .ToListAsync();

        return Ok(suplidores);
    }

    [HttpGet("test-conexion")]
    public async Task<IActionResult> TestConexion()
    {
        try
        {
            var provider = HttpContext.RequestServices.GetRequiredService<CxpApi.Providers.IErpConnectionProvider>();
            var cx = provider.GetConnectionString();
            
            using var conn = new Microsoft.Data.SqlClient.SqlConnection(cx);
            await conn.OpenAsync();
            using var cmd = conn.CreateCommand();
            cmd.CommandText = "SELECT TOP 1 idSuplidor, Nombre FROM cxpsuplidores";
            using var reader = await cmd.ExecuteReaderAsync();
            var result = "";
            if (await reader.ReadAsync())
            {
                result = reader["Nombre"].ToString();
            }
            return Ok(new { success = true, connectionString = cx, suplidor1 = result });
        }
        catch (Exception ex)
        {
            var messages = new List<string>();
            var currentEx = ex;
            while (currentEx != null)
            {
                messages.Add(currentEx.Message);
                currentEx = currentEx.InnerException;
            }
            return BadRequest(new { success = false, errors = messages });
        }
    }

    [HttpGet("catalogos")]
    public async Task<IActionResult> GetCatalogos()
    {
        try
        {
            await _erpDb.Database.OpenConnectionAsync();
            var command = _erpDb.Database.GetDbConnection().CreateCommand();
            
            // cxpTiposSuplidor
            command.CommandText = "SELECT Tiposuplidor, descripcion FROM cxpTiposSuplidor";
            var tiposSuplidor = new List<object>();
            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                {
                    tiposSuplidor.Add(new { Id = reader.GetInt32(0), Nombre = reader.GetString(1) });
                }
            }

            // Moneda
            command.CommandText = "SELECT idMoneda, Moneda FROM Moneda";
            var monedas = new List<object>();
            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                {
                    monedas.Add(new { Id = reader.GetInt32(0), Nombre = reader.GetString(1) });
                }
            }

            // TipoIdentificacion
            command.CommandText = "SELECT idTipoIdentificacion, TipoIdentificacion as Nombre FROM TipoIdentificacion";
            var tiposIdentificacion = new List<object>();
            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                {
                    tiposIdentificacion.Add(new { Id = reader.GetString(0), Nombre = reader.GetString(1) });
                }
            }

            // TipoImpuesto
            command.CommandText = "SELECT idTipoImpuesto, TipoImpuesto as Nombre FROM TipoImpuesto";
            var tiposImpuesto = new List<object>();
            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                {
                    tiposImpuesto.Add(new { Id = reader.GetInt32(0), Nombre = reader.GetString(1) });
                }
            }

            return Ok(new {
                tiposSuplidor,
                monedas,
                tiposIdentificacion,
                tiposImpuesto
            });
        }
        catch (Exception ex)
        {
            return BadRequest(new { mensaje = $"Error al obtener catálogos: {ex.Message}" });
        }
    }

    [HttpGet("verificar-rnc/{rnc}")]
    [AllowAnonymous]
    public async Task<IActionResult> VerificarRnc(string rnc, [FromServices] CxpApi.Services.DgiiService dgiiService)
    {
        try
        {
            // 1. Verificación Local
            var suplidorLocal = await _erpDb.CxpSuplidores
                .Where(s => s.RNC == rnc && (s.Estatus ?? false) == true)
                .Select(s => new
                {
                    s.IdSuplidor,
                    s.Nombre,
                    s.RNC,
                    s.DiasCredito,
                    PedirNCF = s.PedirNCF == "S"
                })
                .FirstOrDefaultAsync();

            if (suplidorLocal != null)
            {
                return Ok(new {
                    existeLocal = true,
                    encontradoDgii = false,
                    datos = suplidorLocal
                });
            }

            // 2. Verificación DGII
            var cmdDefaults = _erpDb.Database.GetDbConnection().CreateCommand();
            cmdDefaults.CommandText = "SELECT valor FROM Defaults WHERE Clave = 'valida_dgii'";
            if (_erpDb.Database.GetDbConnection().State != System.Data.ConnectionState.Open) 
                await _erpDb.Database.OpenConnectionAsync();
            var paramDgiiResult = await cmdDefaults.ExecuteScalarAsync();
            string validaDgiiStr = paramDgiiResult?.ToString() ?? "0";

            if (validaDgiiStr == "1" || validaDgiiStr.ToLower() == "true")
            {
                var dgiiResult = await dgiiService.ConsultarRncAsync(rnc);
                if (dgiiResult != null && dgiiResult.Encontrado && !string.IsNullOrEmpty(dgiiResult.NombreComercial))
                {
                    return Ok(new {
                        existeLocal = false,
                        encontradoDgii = true,
                        nombre = dgiiResult.NombreComercial
                    });
                }
            }
            else
            {
                // Validación Omitida (El parámetro está en '0' o no existe)
                return Ok(new {
                    existeLocal = false,
                    validacionDgiiOmitida = true
                });
            }

            return NotFound(new {
                existeLocal = false,
                encontradoDgii = false,
                mensaje = "RNC no encontrado"
            });
        }
        catch (Exception ex)
        {
            return BadRequest(new { mensaje = $"Error al verificar RNC: {ex.Message}" });
        }
    }

    public class NuevoSuplidorRequest
    {
        public string? Nombre { get; set; }
        public string? RNC { get; set; }
        public int Tiposuplidor { get; set; }
        public int idmoneda { get; set; }
        public string? idTipoIdentificacion { get; set; }
        public int tipoimpuesto { get; set; }
    }

    [HttpPost("rapido")]
    [AllowAnonymous]
    public async Task<IActionResult> CrearSuplidorRapido([FromBody] NuevoSuplidorRequest request)
    {
        if (string.IsNullOrEmpty(request.Nombre))
        {
            return BadRequest("El nombre comercial es obligatorio.");
        }

        try
        {
            await _erpDb.Database.OpenConnectionAsync();

            // Buscar supl_idcuenta
            var cmdDefaults = _erpDb.Database.GetDbConnection().CreateCommand();
            cmdDefaults.CommandText = "SELECT valor FROM Defaults WHERE Clave = 'supl_idcuenta'";
            var defaultCuentaObj = await cmdDefaults.ExecuteScalarAsync();
            string idCuenta = defaultCuentaObj?.ToString() ?? "";

            var command = _erpDb.Database.GetDbConnection().CreateCommand();
            command.CommandText = @"
                INSERT INTO cxpSuplidores (
                    Nombre, RNC, Estatus, MostrarEnCXP, 
                    DiasCredito, PedirNCF, TipoImpuesto, 
                    FechaIngreso, TipoSuplidor, idMoneda, 
                    UidcxpSuplidores,
                    idTipoIdentificacion, idCuenta
                ) 
                VALUES (
                    @Nombre, @RNC, 1, 1, 
                    0, 'S', @TipoImpuesto, 
                    @FechaIngreso, @TipoSuplidor, @idMoneda, 
                    NEWID(),
                    @idTipoIdentificacion, @idCuenta
                );
                SELECT CAST(SCOPE_IDENTITY() as int);
            ";

            var pName = command.CreateParameter();
            pName.ParameterName = "@Nombre";
            pName.Value = request.Nombre;
            command.Parameters.Add(pName);

            var pRNC = command.CreateParameter();
            pRNC.ParameterName = "@RNC";
            pRNC.Value = string.IsNullOrEmpty(request.RNC) ? DBNull.Value : request.RNC;
            command.Parameters.Add(pRNC);

            var pTipoImpuesto = command.CreateParameter();
            pTipoImpuesto.ParameterName = "@TipoImpuesto";
            pTipoImpuesto.Value = request.tipoimpuesto;
            command.Parameters.Add(pTipoImpuesto);

            var pTipoSuplidor = command.CreateParameter();
            pTipoSuplidor.ParameterName = "@TipoSuplidor";
            pTipoSuplidor.Value = request.Tiposuplidor;
            command.Parameters.Add(pTipoSuplidor);

            var pIdMoneda = command.CreateParameter();
            pIdMoneda.ParameterName = "@idMoneda";
            pIdMoneda.Value = request.idmoneda;
            command.Parameters.Add(pIdMoneda);

            var pIdTipoIdent = command.CreateParameter();
            pIdTipoIdent.ParameterName = "@idTipoIdentificacion";
            pIdTipoIdent.Value = string.IsNullOrEmpty(request.idTipoIdentificacion) ? DBNull.Value : request.idTipoIdentificacion;
            command.Parameters.Add(pIdTipoIdent);

            var pIdCuenta = command.CreateParameter();
            pIdCuenta.ParameterName = "@idCuenta";
            pIdCuenta.Value = string.IsNullOrEmpty(idCuenta) ? DBNull.Value : idCuenta;
            command.Parameters.Add(pIdCuenta);

            var pFecha = command.CreateParameter();
            pFecha.ParameterName = "@FechaIngreso";
            pFecha.Value = DateTime.UtcNow;
            command.Parameters.Add(pFecha);

            var resultId = await command.ExecuteScalarAsync();
            int newId = Convert.ToInt32(resultId);

            return Ok(new
            {
                idSuplidor = newId,
                nombre = request.Nombre,
                rnc = request.RNC,
                diasCredito = 0,
                pedirNCF = true
            });
        }
        catch (Exception ex)
        {
            var msg = ex.InnerException?.Message ?? ex.Message;
            return BadRequest(new { mensaje = $"Error creando suplidor rápido: {msg}" });
        }
    }
}
