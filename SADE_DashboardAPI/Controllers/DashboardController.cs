using System;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Authorization;
using SADE_DashboardAPI.Services;
using SADE_DashboardAPI.Models;

namespace SADE_DashboardAPI.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    [Route("[controller]")]
    [Authorize] // PROTECTED BY JWT FROM AUTH-CENTER
    public class DashboardController : ControllerBase
    {
        private readonly IDashboardService _dashboardService;

        public DashboardController(IDashboardService dashboardService)
        {
            _dashboardService = dashboardService;
        }

        [HttpGet("menu")]
        public async Task<IActionResult> GetMenu()
        {
            try
            {
                var menu = await _dashboardService.GetDashboardMenuAsync();
                return Ok(menu);
            }
            catch (Exception ex)
            {
                return StatusCode(500, new { message = "Error al obtener el menú.", error = ex.Message });
            }
        }

        [HttpGet("{idIndicador}")]
        public async Task<IActionResult> Get(int idIndicador, [FromQuery] DateTime fechaDesde, [FromQuery] DateTime fechaHasta)
        {
            try
            {
                var result = await _dashboardService.GetDashboardDataAsync(idIndicador, fechaDesde, fechaHasta);

                if (result == null)
                {
                    return NotFound(new { message = $"Indicador con Id {idIndicador} no encontrado." });
                }

                return Ok(result);
            }
            catch (Exception ex)
            {
                // En un escenario real, deberíamos registrar el error (logging)
                return StatusCode(500, new { message = "Ocurrió un error al procesar la solicitud.", error = ex.Message });
            }
        }
    }
}
