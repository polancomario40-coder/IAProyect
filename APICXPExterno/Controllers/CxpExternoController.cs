using CxpApi.Filters;
using CxpApi.Models;
using CxpApi.Services;
using Microsoft.AspNetCore.Mvc;

namespace CxpApi.Controllers;

[ApiController]
[Route("api/[controller]")]
public class CxpExternoController : ControllerBase
{
    private readonly ICxpExternoService _cxpExternoService;

    public CxpExternoController(ICxpExternoService cxpExternoService)
    {
        _cxpExternoService = cxpExternoService;
    }

    [HttpPost("factura")]
    [ApiKeyAuth]
    public async Task<IActionResult> IntegrarFactura([FromBody] CxpFacturaExternaDto dto)
    {
        if (!ModelState.IsValid)
        {
            return BadRequest(ResultadoOperacion.Fallido("Datos de entrada inválidos."));
        }

        var result = await _cxpExternoService.ProcesarFacturaExternaAsync(dto);

        if (result.Exito)
        {
            return Ok(result);
        }
        else
        {
            return BadRequest(result);
        }
    }
}
