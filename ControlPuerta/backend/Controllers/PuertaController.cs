using ControlPuertaAPI.Models;
using ControlPuertaAPI.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;

namespace ControlPuertaAPI.Controllers;

/// <summary>
/// FASE 1 — Control de Puerta (Entrada de Mercancía con IA)
/// Endpoints:
///   POST   /api/puerta/ocr-placa              → Extraer texto de placa con Azure AI
///   GET    /api/puerta/validar-transportista   → Buscar transportista por placa
///   POST   /api/puerta/registrar-entrada       → Registrar entrada en BD
///   GET    /api/puerta/entradas-hoy            → Monitor de entradas del día
/// </summary>
[ApiController]
[Route("api/puerta")]
[Authorize]
public class PuertaController : ControllerBase
{
    private readonly IOcrService _ocr;
    private readonly IPuertaDbService _db;
    private readonly ILogger<PuertaController> _logger;
    private readonly IConfiguration _config;

    public PuertaController(
        IOcrService ocr,
        IPuertaDbService db,
        ILogger<PuertaController> logger,
        IConfiguration config)
    {
        _ocr    = ocr;
        _db     = db;
        _logger = logger;
        _config = config;
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/puerta/configuracion  (público, sin token)
    // Retorna companiacorto de la tabla Configuracion del ERP
    // ──────────────────────────────────────────────────────────────────────────
    [AllowAnonymous]
    [HttpGet("configuracion")]
    public async Task<IActionResult> ObtenerConfiguracion()
    {
        try
        {
            var conf = await _db.ObtenerConfiguracionAsync();
            return Ok(ApiResponse<object>.Ok(conf, "OK"));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error obteniendo configuración");
            return Ok(ApiResponse<object>.Ok(new { CompaniaCorto = "SADE" }, "Fallback"));
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/puerta/configuracion/logo  (público, sin token)
    // Retorna el logo de la empresa como imagen binaria
    // ──────────────────────────────────────────────────────────────────────────
    [AllowAnonymous]
    [HttpGet("configuracion/logo")]
    public async Task<IActionResult> ObtenerLogo()
    {
        try
        {
            var logoBytes = await _db.ObtenerLogoAsync();
            if (logoBytes != null && logoBytes.Length > 0)
                return File(logoBytes, "image/png");
            return NotFound();
        }
        catch
        {
            return NotFound();
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/puerta/ocr-placa
    // Recibe imagen en base64, llama a Azure AI Document Intelligence,
    // retorna el texto de la placa detectado.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpPost("ocr-placa")]
    public async Task<ActionResult<ApiResponse<OcrPlacaResponse>>> OcrPlaca([FromBody] OcrPlacaRequest req)
    {
        if (string.IsNullOrWhiteSpace(req.ImagenBase64))
            return BadRequest(ApiResponse<OcrPlacaResponse>.Fail("La imagen en base64 es requerida."));

        // Validar tamaño máximo de imagen
        var maxSize = _config.GetValue<int>("ControlPuerta:MaxImageSizeBytes", 5_242_880); // 5 MB default
        var imageBytes = Convert.FromBase64String(
            req.ImagenBase64.Contains(',') ? req.ImagenBase64[(req.ImagenBase64.IndexOf(',') + 1)..] : req.ImagenBase64
        );
        if (imageBytes.Length > maxSize)
            return BadRequest(ApiResponse<OcrPlacaResponse>.Fail($"La imagen supera el tamaño máximo de {maxSize / 1_048_576} MB."));

        var resultado = await _ocr.ExtraerTextoPlacaAsync(req.ImagenBase64, req.MimeType);
        return Ok(ApiResponse<OcrPlacaResponse>.Ok(resultado,
            resultado.Exito ? "Texto extraído correctamente." : resultado.Mensaje ?? "No se pudo extraer texto."));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/puerta/validar-transportista?placa=A123456
    // Busca transportista en BD a partir de la placa.
    // Si no existe → 404 con mensaje amigable.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("validar-transportista")]
    public async Task<ActionResult<ApiResponse<TransportistaDto>>> ValidarTransportista([FromQuery] string placa)
    {
        if (string.IsNullOrWhiteSpace(placa))
            return BadRequest(ApiResponse<TransportistaDto>.Fail("El número de placa es requerido."));

        var transportista = await _db.BuscarTransportistaPorPlacaAsync(placa.Trim().ToUpper());

        if (transportista is null)
            return NotFound(ApiResponse<TransportistaDto>.Fail(
                $"No se encontró ningún transportista activo con la placa '{placa.ToUpper()}'. " +
                "Verifique la placa o registre el transportista en el sistema."));

        return Ok(ApiResponse<TransportistaDto>.Ok(transportista,
            $"Transportista '{transportista.Nombre}' encontrado. Puede proceder con la entrada."));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/puerta/buscar-placas
    // Autocompletado de placas
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("buscar-placas")]
    public async Task<ActionResult<ApiResponse<List<string>>>> BuscarPlacas([FromQuery] string q)
    {
        var placas = await _db.BuscarPlacasAsync(q);
        return Ok(ApiResponse<List<string>>.Ok(placas));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/puerta/productos
    // Lista productos de la tabla invProductoPuerta
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("productos")]
    public async Task<ActionResult<ApiResponse<List<ProductoDto>>>> ListarProductos()
    {
        var productos = await _db.ListarProductosAsync();
        return Ok(ApiResponse<List<ProductoDto>>.Ok(productos));
    }

    // ─────────────────────────────────────────────────────────────────────────
    // GET /api/puerta/productos-reales
    // Búsqueda de productos reales del ERP (Materia prima)
    // ─────────────────────────────────────────────────────────────────────────
    [HttpGet("productos-reales")]
    public async Task<ActionResult<ApiResponse<List<ProductoDto>>>> BuscarProductosReales([FromQuery] string q = "")
    {
        var productos = await _db.BuscarProductosRealesAsync(q);
        return Ok(ApiResponse<List<ProductoDto>>.Ok(productos));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/puerta/choferes/{idTransportista}
    // Lista choferes activos de un transportista (para selector en formulario)
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("choferes/{idTransportista}")]
    public async Task<ActionResult<ApiResponse<List<ChoferDto>>>> ListarChoferes(string idTransportista)
    {
        var choferes = await _db.ListarChoferesPorTransportistaAsync(idTransportista);
        return Ok(ApiResponse<List<ChoferDto>>.Ok(choferes));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/puerta/registrar-entrada
    // Guarda la entrada del camión en prtEntradaCamion (+ detalle de productos).
    // NO requiere OC previa — regla de negocio explícita.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpPost("registrar-entrada")]
    public async Task<ActionResult<ApiResponse<object>>> RegistrarEntrada([FromBody] RegistrarEntradaRequest req)
    {
        // Validaciones de negocio
        if (string.IsNullOrWhiteSpace(req.Conduce))
            return BadRequest(ApiResponse<object>.Fail("El número de conduce es requerido."));
        if (string.IsNullOrWhiteSpace(req.Placa))
            return BadRequest(ApiResponse<object>.Fail("La placa del camión es requerida."));

        var usuario = ObtenerUsuario();
        try 
        {
            var idEntrada = await _db.RegistrarEntradaAsync(req, usuario);
            return Ok(ApiResponse<object>.Ok(
                new { idEntradaCamion = idEntrada },
                $"Entrada del conduce '{req.Conduce}' registrada exitosamente."));
        }
        catch (Exception ex)
        {
            if (ex.Message.Contains("Ya existe una entrada registrada"))
                return BadRequest(ApiResponse<object>.Fail(ex.Message));
            
            throw;
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/puerta/entradas-hoy?idPuerta=PUERTA1
    // Lista las últimas 50 entradas del día para el monitor de la pantalla.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("entradas-hoy")]
    public async Task<ActionResult<ApiResponse<List<EntradaCamionDto>>>> EntradasHoy([FromQuery] string? idPuerta)
    {
        // Entradas pendientes del día: NO se filtra por almacén del usuario
        // (la asignación de almacén ocurre durante la recepción, no en el registro)
        var entradas = await _db.ObtenerEntradasHoyAsync(idPuerta);
        return Ok(ApiResponse<List<EntradaCamionDto>>.Ok(entradas,
            $"{entradas.Count} entradas registradas hoy."));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // PUT /api/puerta/{id}/cancelar
    // Cancela una entrada que está pendiente.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpPut("{id:guid}/cancelar")]
    public async Task<ActionResult<ApiResponse<object>>> CancelarEntrada(Guid id)
    {
        var usuario = ObtenerUsuario();
        var cancelado = await _db.CancelarEntradaAsync(id, usuario);

        if (!cancelado)
            return BadRequest(ApiResponse<object>.Fail("No se pudo cancelar la entrada. Verifique que exista y esté en estado PENDIENTE."));

        return Ok(ApiResponse<object>.Ok(new { idEntradaCamion = id }, "Entrada cancelada correctamente."));
    }

    // ── Helper ────────────────────────────────────────────────────────────────
    private string ObtenerUsuario()
        => User.FindFirst(ClaimTypes.Name)?.Value
        ?? User.FindFirst("sub")?.Value
        ?? User.FindFirst("idSegUserGrp")?.Value
        ?? "SISTEMA";
}
