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

    public class NuevoSuplidorRequest
    {
        public string? Nombre { get; set; }
        public string? RNC { get; set; }
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
            var command = _erpDb.Database.GetDbConnection().CreateCommand();
            command.CommandText = @"
                INSERT INTO cxpSuplidores (
                    Nombre, RNC, Estatus, MostrarEnCXP, 
                    DiasCredito, PedirNCF, TipoImpuesto, 
                    FechaIngreso, TipoSuplidor, idMoneda, 
                    UidcxpSuplidores, EvalRefComerciales, EvalCapacidad, 
                    EvalCertificaciones, EvalTiempoMercado, EvalServicios, 
                    IncluirEnLista, EvalPorAuditoria, OtraAccion
                ) 
                VALUES (
                    @Nombre, @RNC, 1, 1, 
                    0, 'S', 1, 
                    @FechaIngreso, 1, 1, 
                    NEWID(), 0, 0, 
                    0, 0, 0, 
                    0, 0, 0
                );
                SELECT CAST(SCOPE_IDENTITY() as int);
            ";

            await _erpDb.Database.OpenConnectionAsync();

            var pName = command.CreateParameter();
            pName.ParameterName = "@Nombre";
            pName.Value = request.Nombre;
            command.Parameters.Add(pName);

            var pRNC = command.CreateParameter();
            pRNC.ParameterName = "@RNC";
            pRNC.Value = string.IsNullOrEmpty(request.RNC) ? DBNull.Value : request.RNC;
            command.Parameters.Add(pRNC);

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
