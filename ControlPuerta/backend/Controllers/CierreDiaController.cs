using ControlPuertaAPI.Models;
using ControlPuertaAPI.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;

namespace ControlPuertaAPI.Controllers;

/// <summary>
/// FASE 3 — Consulta y Cierre Diario
/// Endpoints:
///   GET    /api/cierre/recepciones              → Datatable con filtros múltiples
///   GET    /api/cierre/pendientes?fecha=        → Recepciones sin OC del día
///   PUT    /api/cierre/asignar-oc              → Asignar OC a una entrada
///   POST   /api/cierre/ejecutar                → Ejecutar cierre del día
///   GET    /api/cierre/ordenes?q=              → Buscar órdenes de compra para asignar
/// </summary>
[ApiController]
[Route("api/cierre")]
[Authorize]
public class CierreDiaController : ControllerBase
{
    private readonly IPuertaDbService _db;
    private readonly ILogger<CierreDiaController> _logger;
    private readonly IConnectionFactory _cf;

    public CierreDiaController(
        IPuertaDbService db,
        ILogger<CierreDiaController> logger,
        IConnectionFactory cf)
    {
        _db     = db;
        _logger = logger;
        _cf     = cf;
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/cierre/recepciones
    // Datatable filtrable con todas las recepciones históricas.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("recepciones")]
    public async Task<ActionResult<ApiResponse<object>>> ConsultarRecepciones([FromQuery] ConsultaFiltros filtros)
    {
        var usuario = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value 
                      ?? User.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value;
        filtros.UsuarioPermiso = usuario;

        var lista = await _db.ConsultarRecepcionesAsync(filtros);
        var total = lista.FirstOrDefault()?.TotalRegistros ?? 0;

        return Ok(ApiResponse<object>.Ok(new
        {
            data       = lista,
            pageNumber = filtros.PageNumber,
            pageSize   = filtros.PageSize,
            total
        }));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/cierre/pendientes?fecha=2026-08-23
    // Lista las recepciones del día que aún no tienen OC asignada.
    // Estas son las que el usuario debe gestionar antes del cierre.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("pendientes")]
    public async Task<ActionResult<ApiResponse<List<EntradaCamionDto>>>> ObtenerPendientes(
        [FromQuery] DateOnly? fecha)
    {
        var fechaDia = fecha ?? DateOnly.FromDateTime(DateTime.Today);
        var pendientes = await _db.ObtenerPendientesCierreAsync(fechaDia);

        var sinOc  = pendientes.Count(p => p.IdOrden is null);
        var conOc  = pendientes.Count(p => p.IdOrden is not null);

        return Ok(ApiResponse<List<EntradaCamionDto>>.Ok(pendientes,
            $"Día {fechaDia:dd/MM/yyyy}: {pendientes.Count} recepciones ({conOc} con OC, {sinOc} sin OC)."));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // PUT /api/cierre/asignar-oc
    // Asigna una Orden de Compra a una entrada específica.
    // Puede llamarse múltiples veces antes del cierre.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpPut("asignar-oc")]
    public async Task<ActionResult<ApiResponse<object>>> AsignarOc([FromBody] AsignarOcRequest req)
    {
        if (req.IdEntradaCamion == Guid.Empty)
            return BadRequest(ApiResponse<object>.Fail("IdEntradaCamion requerido."));
        if (req.IdOrden == Guid.Empty)
            return BadRequest(ApiResponse<object>.Fail("IdOrden requerido."));

        var usuario = ObtenerUsuario();
        var ok = await _db.AsignarOrdenAsync(req, usuario);

        if (!ok)
            return NotFound(ApiResponse<object>.Fail("No se encontró la entrada especificada."));

        return Ok(ApiResponse<object>.Ok(
            new { idEntradaCamion = req.IdEntradaCamion, idOrden = req.IdOrden },
            $"OC #{req.OrdenNumero} asignada correctamente."));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/cierre/ejecutar
    // Proceso de cierre del día:
    //  - REGLA CRÍTICA: Entradas SIN OC quedan en status BLOQUEADO → no van a CxP
    //  - Entradas CON OC quedan en status CERRADO
    // ──────────────────────────────────────────────────────────────────────────
    [HttpPost("ejecutar")]
    public async Task<ActionResult<ApiResponse<CierreDiaResultDto>>> EjecutarCierre(
        [FromBody] EjecutarCierreRequest req)
    {
        var fechaDia = req.FechaDia;
        var usuario  = ObtenerUsuario();

        // 1. Aplicar asignaciones de OC que vengan en el request del cierre
        foreach (var asign in req.AsignacionesOc)
        {
            await _db.AsignarOrdenAsync(asign, usuario);
        }

        // 2. Verificar que no haya ya un cierre para este día
        var existeCierre = await ExisteCierreParaDiaAsync(fechaDia);
        if (existeCierre)
            return Conflict(ApiResponse<CierreDiaResultDto>.Fail(
                $"Ya existe un cierre registrado para el día {fechaDia:dd/MM/yyyy}."));

        // 3. Ejecutar cierre
        var resultado = await _db.EjecutarCierreDiaAsync(fechaDia, usuario, req.Notas);

        _logger.LogInformation("[CIERRE] Día {Fecha} cerrado por {Usuario}. Total: {Tot}, Con OC: {COC}, Sin OC: {SOC}",
            fechaDia, usuario, resultado.TotalRecepciones, resultado.TotalConOC, resultado.TotalSinOC);

        var mensaje = $"Cierre del día {fechaDia:dd/MM/yyyy} ejecutado. " +
                      $"{resultado.TotalConOC} recepciones cerradas" +
                      (resultado.TotalSinOC > 0
                          ? $", {resultado.TotalSinOC} BLOQUEADAS por falta de OC (no procederán a CxP)."
                          : ".");

        return Ok(ApiResponse<CierreDiaResultDto>.Ok(resultado, mensaje));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/cierre/ordenes?q=&fecha=
    // Busca Órdenes de Compra del ERP para asignar durante el cierre.
    // Filtra por número o suplidor. Solo devuelve OC en status APROBADO.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("ordenes")]
    public async Task<ActionResult<ApiResponse<List<object>>>> BuscarOrdenes(
        [FromQuery] string? q, [FromQuery] DateOnly? fecha)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            SELECT TOP 30
                o.idOrden,
                o.Numero,
                o.Fecha,
                s.Nombre AS Suplidor,
                o.Status,
                o.GranTotal,
                o.Notas
            FROM ocOrdenes o
            LEFT JOIN cxpSuplidores s ON s.IdSuplidor = o.idSuplidor
            WHERE o.Status IN ('A','P')
              AND (@q IS NULL OR
                   CAST(o.Numero AS VARCHAR) LIKE '%' + @q + '%' OR
                   s.Nombre LIKE '%' + @q + '%')
              AND (@fecha IS NULL OR CAST(o.Fecha AS DATE) = @fecha)
            ORDER BY o.Numero DESC";

        cmd.Parameters.AddWithValue("@q",     (object?)q     ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@fecha", (object?)(fecha.HasValue ? fecha.Value.ToDateTime(TimeOnly.MinValue) : null) ?? DBNull.Value);

        var lista = new List<object>();
        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            lista.Add(new
            {
                idOrden    = reader.GetGuid(0),
                numero     = reader.GetInt32(1),
                fecha      = reader.GetDateTime(2),
                suplidor   = reader.IsDBNull(3) ? "" : reader.GetString(3),
                status     = reader.GetString(4),
                granTotal  = reader.IsDBNull(5) ? 0m : reader.GetDecimal(5),
                notas      = reader.IsDBNull(6) ? "" : reader.GetString(6)
            });
        }

        return Ok(ApiResponse<List<object>>.Ok(lista));
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private string ObtenerUsuario()
        => User.FindFirst(ClaimTypes.Name)?.Value
        ?? User.FindFirst("sub")?.Value
        ?? User.FindFirst("idSegUserGrp")?.Value
        ?? "SISTEMA";

    private async Task<bool> ExisteCierreParaDiaAsync(DateOnly fechaDia)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT COUNT(1) FROM prtCierreDia WHERE FechaDia = @f";
        cmd.Parameters.AddWithValue("@f", fechaDia.ToDateTime(TimeOnly.MinValue));
        return (int)(await cmd.ExecuteScalarAsync() ?? 0) > 0;
    }
}
