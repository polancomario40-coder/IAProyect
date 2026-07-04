using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using CxpApi.Data;
using System.Data;
using System.Data.Common;

namespace CxpApi.Controllers;

[ApiController]
[Route("api/monedas")]
[Authorize]
public class MonedaController : ControllerBase
{
    private readonly AppDbContext _erpDb;

    public MonedaController(AppDbContext erpDb)
    {
        _erpDb = erpDb;
    }

    [HttpGet]
    public async Task<IActionResult> GetMonedas()
    {
        var monedas = new List<object>();
        
        try
        {
            var command = _erpDb.Database.GetDbConnection().CreateCommand();
            // Filtrar CursoLegal según sea necesario, aquí traemos todas o las más relevantes.
            command.CommandText = "SELECT idMoneda, Moneda FROM Moneda ORDER BY idMoneda"; 
            
            await _erpDb.Database.OpenConnectionAsync();
            using (var result = await command.ExecuteReaderAsync())
            {
                while (await result.ReadAsync())
                {
                    monedas.Add(new
                    {
                        IdMoneda = result.GetInt32(0),
                        Nombre = result.GetString(1)
                    });
                }
            }
            return Ok(monedas);
        }
        catch (Exception ex)
        {
            return BadRequest(new { mensaje = $"Error al consultar monedas: {ex.Message}" });
        }
    }
}
