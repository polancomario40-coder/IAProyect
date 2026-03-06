using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using CxpApi.Data;
using System.Data;
using System.Data.Common;

namespace CxpApi.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class ClaseGastoController : ControllerBase
{
    private readonly AppDbContext _erpDb;

    public ClaseGastoController(AppDbContext erpDb)
    {
        _erpDb = erpDb;
    }

    [HttpGet]
    public async Task<IActionResult> GetClasesGasto()
    {
        var clases = new List<object>();
        
        try
        {
            var command = _erpDb.Database.GetDbConnection().CreateCommand();
            command.CommandText = "SELECT idClasegasto, ClaseGasto FROM cxpClaseGasto"; // Removemos filtro Activo si no existe
            
            await _erpDb.Database.OpenConnectionAsync();
            using (var result = await command.ExecuteReaderAsync())
            {
                while (await result.ReadAsync())
                {
                    clases.Add(new
                    {
                        IdClasegasto = result.GetString(0),
                        ClaseGasto = result.GetString(1)
                    });
                }
            }
            return Ok(clases);
        }
        catch (Exception ex)
        {
            return BadRequest($"Error al consultar tipo de gastos: {ex.Message}");
        }
    }
}
