using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using CxpApi.Data;
using System.Data;
using System.Data.Common;

namespace CxpApi.Controllers;

[ApiController]
[Route("api/formaspago")]
[Authorize]
public class PagoFormaController : ControllerBase
{
    private readonly AppDbContext _erpDb;

    public PagoFormaController(AppDbContext erpDb)
    {
        _erpDb = erpDb;
    }

    [HttpGet]
    public async Task<IActionResult> GetFormasPago()
    {
        var formas = new List<object>();
        
        try
        {
            var command = _erpDb.Database.GetDbConnection().CreateCommand();
            command.CommandText = "SELECT idPagoForma, PagoForma FROM PagoFormaCxP ORDER BY idPagoForma"; 
            
            await _erpDb.Database.OpenConnectionAsync();
            using (var result = await command.ExecuteReaderAsync())
            {
                while (await result.ReadAsync())
                {
                    formas.Add(new
                    {
                        IdPagoForma = result.GetInt32(0),
                        Nombre = result.GetString(1) // El nombre de la columna es PagoForma
                    });
                }
            }
            return Ok(formas);
        }
        catch (Exception ex)
        {
            return BadRequest(new { mensaje = $"Error al consultar formas de pago: {ex.Message}" });
        }
    }
}
