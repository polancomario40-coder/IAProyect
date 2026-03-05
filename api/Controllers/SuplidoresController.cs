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
            .Where(s => s.Estatus == true && s.MostrarEnCXP == true)
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
}
