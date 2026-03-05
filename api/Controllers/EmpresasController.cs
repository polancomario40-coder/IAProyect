using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using CxpApi.Data;

namespace CxpApi.Controllers;

[ApiController]
[Route("api/[controller]")]
public class EmpresasController : ControllerBase
{
    private readonly AuthDbContext _authDb;

    public EmpresasController(AuthDbContext authDb)
    {
        _authDb = authDb;
    }

    [HttpGet]
    public async Task<IActionResult> GetEmpresas()
    {
        var empresas = await _authDb.Empresas
            .Where(e => e.Activa && e.AccesoWeb)
            .Select(e => new
            {
                e.IdEmpresa,
                e.Empresa,
                e.RNC
            })
            .ToListAsync();

        return Ok(empresas);
    }
}
