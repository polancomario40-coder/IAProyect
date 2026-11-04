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
    private readonly IOcrService _ocr;
    private readonly IConnectionFactory _cf;
    private readonly ILogger<ConciliacionController> _logger;

    public ConciliacionController(
        IPuertaDbService db, 
        IOcrService ocr, 
        IConnectionFactory cf,
        ILogger<ConciliacionController> logger)
    {
        _db     = db;
        _ocr    = ocr;
        _cf     = cf;
        _logger = logger;
    }

    private string ObtenerUsuario()
        => User.FindFirst(ClaimTypes.NameIdentifier)?.Value
        ?? User.FindFirst("sub")?.Value
        ?? User.Identity?.Name
        ?? "SISTEMA";

    private async Task<bool> EsUsuarioAutorizadoAsync()
    {
        var usuario = ObtenerUsuario();
        if (string.IsNullOrWhiteSpace(usuario) || usuario.Equals("SISTEMA", StringComparison.OrdinalIgnoreCase))
            return true;

        try
        {
            await using var conn = _cf.CreateErpConnection();
            await conn.OpenAsync();
            await using var cmd = conn.CreateCommand();
            cmd.CommandText = @"
                SELECT COUNT(1)
                FROM SegUserinGrp
                WHERE idSegUser = @usuario
                  AND (
                    LOWER(idSegGrupo) LIKE '%conta%' 
                    OR LOWER(idSegGrupo) LIKE '%admin%'
                  );";
            cmd.Parameters.AddWithValue("@usuario", usuario.Trim());
            var count = Convert.ToInt32(await cmd.ExecuteScalarAsync());
            return count > 0;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "[Conciliacion] Error verificando roles de usuario {Usuario}. Permitiendo acceso por contingencia.", usuario);
            return true;
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/conciliacion/extraer-documento
    // Extrae conduces desde un PDF escaneado o Imagen mediante Azure AI OCR
    // ──────────────────────────────────────────────────────────────────────────
    [HttpPost("extraer-documento")]
    [RequestSizeLimit(30_000_000)]
    public async Task<ActionResult<ApiResponse<List<ItemConciliacionInputDto>>>> ExtraerDocumento()
    {
        if (!await EsUsuarioAutorizadoAsync())
            return StatusCode(StatusCodes.Status403Forbidden, ApiResponse<List<ItemConciliacionInputDto>>.Fail("Acceso restringido: Este módulo es exclusivo para usuarios de los grupos Contabilidad o Administrador."));

        byte[] fileBytes;
        string mimeType = "application/pdf";
        string fileName = "documento";

        try
        {
            if (Request.HasFormContentType && Request.Form.Files.Count > 0)
            {
                var file = Request.Form.Files[0];
                fileName = file.FileName;
                mimeType = string.IsNullOrWhiteSpace(file.ContentType) ? "application/pdf" : file.ContentType;
                using var ms = new MemoryStream();
                await file.CopyToAsync(ms);
                fileBytes = ms.ToArray();
            }
            else
            {
                using var reader = new StreamReader(Request.Body);
                var bodyStr = await reader.ReadToEndAsync();
                if (string.IsNullOrWhiteSpace(bodyStr))
                    return BadRequest(ApiResponse<List<ItemConciliacionInputDto>>.Fail("No se recibió ningún archivo o cuerpo de solicitud."));

                var docReq = System.Text.Json.JsonSerializer.Deserialize<ExtraerDocumentoRequest>(
                    bodyStr, 
                    new System.Text.Json.JsonSerializerOptions { PropertyNameCaseInsensitive = true }
                );

                if (docReq == null || string.IsNullOrWhiteSpace(docReq.Base64))
                    return BadRequest(ApiResponse<List<ItemConciliacionInputDto>>.Fail("Contenido del archivo no provisto."));

                fileBytes = Convert.FromBase64String(docReq.Base64);
                mimeType = docReq.MimeType ?? "application/pdf";
                fileName = docReq.NombreArchivo ?? "documento.pdf";
            }

            if (fileBytes == null || fileBytes.Length == 0)
                return BadRequest(ApiResponse<List<ItemConciliacionInputDto>>.Fail("El archivo enviado está vacío."));

            var items = await _ocr.ExtraerConducesDeDocumentoAsync(fileBytes, mimeType);
            return Ok(ApiResponse<List<ItemConciliacionInputDto>>.Ok(
                items, 
                $"Se extrajeron {items.Count} conduces del documento '{fileName}'."));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error extrayendo conduces del documento");
            return StatusCode(500, ApiResponse<List<ItemConciliacionInputDto>>.Fail("Error procesando OCR del documento: " + ex.Message));
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/conciliacion/comparar
    // Recibe la lista de conduces extraída del Excel y la compara contra el sistema.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpPost("comparar")]
    public async Task<ActionResult<ApiResponse<ResultadoConciliacionDto>>> Comparar([FromBody] CompararConciliacionRequest req)
    {
        if (!await EsUsuarioAutorizadoAsync())
            return StatusCode(StatusCodes.Status403Forbidden, ApiResponse<ResultadoConciliacionDto>.Fail("Acceso restringido: Este módulo es exclusivo para usuarios de los grupos Contabilidad o Administrador."));

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
        if (!await EsUsuarioAutorizadoAsync())
            return StatusCode(StatusCodes.Status403Forbidden, ApiResponse<object>.Fail("Acceso restringido: Este módulo es exclusivo para usuarios de los grupos Contabilidad o Administrador."));

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
        if (!await EsUsuarioAutorizadoAsync())
            return StatusCode(StatusCodes.Status403Forbidden, ApiResponse<List<LoteConciliacionDto>>.Fail("Acceso restringido: Este módulo es exclusivo para usuarios de los grupos Contabilidad o Administrador."));

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
        if (!await EsUsuarioAutorizadoAsync())
            return StatusCode(StatusCodes.Status403Forbidden, ApiResponse<ResultadoConciliacionDto>.Fail("Acceso restringido: Este módulo es exclusivo para usuarios de los grupos Contabilidad o Administrador."));

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
        if (!await EsUsuarioAutorizadoAsync())
            return StatusCode(StatusCodes.Status403Forbidden, ApiResponse<bool>.Fail("Acceso restringido: Este módulo es exclusivo para usuarios de los grupos Contabilidad o Administrador."));

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
