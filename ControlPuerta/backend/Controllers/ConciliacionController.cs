using ControlPuertaAPI.Models;
using ControlPuertaAPI.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;

namespace ControlPuertaAPI.Controllers;

/// <summary>
/// Módulo de Conciliación de Conduces de Suplidores y Flujo de Pagos (CXP)
/// </summary>
[ApiController]
[Route("api/conciliacion")]
[Authorize]
public class ConciliacionController : ControllerBase
{
    private readonly IPuertaDbService _db;
    private readonly ILogger<ConciliacionController> _logger;

    public ConciliacionController(IPuertaDbService db, ILogger<ConciliacionController> logger)
    {
        _db     = db;
        _logger = logger;
    }

    private string ObtenerUsuario()
        => User.FindFirst(ClaimTypes.NameIdentifier)?.Value
        ?? User.FindFirst("sub")?.Value
        ?? User.Identity?.Name
        ?? "SISTEMA";

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/conciliacion/comparar
    // Recibe la lista de conduces extraída del Excel y la compara contra el sistema.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpPost("comparar")]
    public async Task<ActionResult<ApiResponse<ResultadoConciliacionDto>>> Comparar([FromBody] CompararConciliacionRequest req)
    {
        if (req == null || req.Items == null || req.Items.Count == 0)
            return BadRequest(ApiResponse<ResultadoConciliacionDto>.Fail("No se enviaron datos de conduces para conciliar."));

        if (string.IsNullOrWhiteSpace(req.Suplidor))
            return BadRequest(ApiResponse<ResultadoConciliacionDto>.Fail("Debe especificar o seleccionar el Suplidor."));

        var usuario = ObtenerUsuario();
        try
        {
            var resultado = await _db.CompararConducesAsync(req, usuario);
            return Ok(ApiResponse<ResultadoConciliacionDto>.Ok(resultado, 
                $"Análisis completado: {resultado.TotalCalifican} califican para pago, {resultado.TotalRechazados} con discrepancias, {resultado.TotalPendientes} pendientes de recepción."));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error al ejecutar comparación de conduces");
            return StatusCode(500, ApiResponse<ResultadoConciliacionDto>.Fail("Error interno al comparar conduces: " + ex.Message));
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/conciliacion/guardar
    // Guarda el lote analizado y sus filas en base de datos.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpPost("guardar")]
    public async Task<ActionResult<ApiResponse<object>>> Guardar([FromBody] GuardarConciliacionRequest req)
    {
        if (req == null || req.Items == null || req.Items.Count == 0)
            return BadRequest(ApiResponse<object>.Fail("No hay items para guardar en la conciliación."));

        var usuario = ObtenerUsuario();
        try
        {
            var idConciliacion = await _db.GuardarLoteConciliacionAsync(req, usuario);
            return Ok(ApiResponse<object>.Ok(new { idConciliacion }, "Lote de conciliación guardado exitosamente."));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error al guardar lote de conciliación");
            return StatusCode(500, ApiResponse<object>.Fail("Error al guardar lote: " + ex.Message));
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/conciliacion/lotes
    // Historial de lotes de conciliación registrados
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("lotes")]
    public async Task<ActionResult<ApiResponse<List<LoteConciliacionDto>>>> ListarLotes(
        [FromQuery] string? idSuplidor, 
        [FromQuery] string? status)
    {
        try
        {
            var lista = await _db.ListarLotesConciliacionAsync(idSuplidor, status);
            return Ok(ApiResponse<List<LoteConciliacionDto>>.Ok(lista));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error al listar lotes de conciliación");
            return StatusCode(500, ApiResponse<List<LoteConciliacionDto>>.Fail(ex.Message));
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/conciliacion/lotes/{id}
    // Detalle completo de un lote con cada uno de sus conduces y estados
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("lotes/{id}")]
    public async Task<ActionResult<ApiResponse<ResultadoConciliacionDto>>> ObtenerLote(Guid id)
    {
        try
        {
            var lote = await _db.ObtenerLoteConciliacionAsync(id);
            if (lote == null)
                return NotFound(ApiResponse<ResultadoConciliacionDto>.Fail("Lote de conciliación no encontrado."));

            return Ok(ApiResponse<ResultadoConciliacionDto>.Ok(lote));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error al obtener detalle del lote {Id}", id);
            return StatusCode(500, ApiResponse<ResultadoConciliacionDto>.Fail(ex.Message));
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // PUT /api/conciliacion/lotes/{id}/estado-pago
    // Actualiza el estado de pago del lote o conduces seleccionados (Flujo CXP)
    // ──────────────────────────────────────────────────────────────────────────
    [HttpPut("lotes/{id}/estado-pago")]
    public async Task<ActionResult<ApiResponse<bool>>> ActualizarEstadoPago(
        Guid id, 
        [FromBody] ActualizarEstadoPagoRequest req)
    {
        if (string.IsNullOrWhiteSpace(req.NuevoEstadoPago))
            return BadRequest(ApiResponse<bool>.Fail("Debe especificar el nuevo estado de pago (APROBADO, PAGADO, etc.)."));

        var usuario = ObtenerUsuario();
        try
        {
            var ok = await _db.ActualizarEstadoPagoLoteAsync(id, req, usuario);
            return Ok(ApiResponse<bool>.Ok(ok, $"Estado de pago actualizado a '{req.NuevoEstadoPago}' exitosamente."));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error al actualizar estado de pago para el lote {Id}", id);
            return StatusCode(500, ApiResponse<bool>.Fail(ex.Message));
        }
    }
}
