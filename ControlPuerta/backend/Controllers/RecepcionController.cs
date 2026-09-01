using ControlPuertaAPI.Models;
using ControlPuertaAPI.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;
using System.Text;

namespace ControlPuertaAPI.Controllers;

/// <summary>
/// FASE 2 — Recepción de Conduces y Evidencias
/// Endpoints:
///   GET    /api/recepcion/{id}              → Obtener detalle de una entrada
///   PUT    /api/recepcion/{id}/confirmar    → Almacenista confirma recepción
///   POST   /api/recepcion/{id}/evidencia    → Guardar foto + firma
///   POST   /api/recepcion/{id}/notificar    → Enviar email con conduce firmado
///   GET    /api/recepcion/{id}/ticket       → Datos para ticket de impresión
///   GET    /api/recepcion/{id}/evidencia/{tipo} → Descargar imagen binaria
/// </summary>
[ApiController]
[Route("api/recepcion")]
[Authorize]
public class RecepcionController : ControllerBase
{
    private readonly IPuertaDbService _db;
    private readonly IEvidenciaService _evidencias;
    private readonly IEmailService _email;
    private readonly ILogger<RecepcionController> _logger;
    private readonly IConfiguration _config;
    private readonly IHttpContextAccessor _httpContextAccessor;

    public RecepcionController(
        IPuertaDbService db,
        IEvidenciaService evidencias,
        IEmailService email,
        ILogger<RecepcionController> logger,
        IConfiguration config,
        IHttpContextAccessor httpContextAccessor)
    {
        _db                 = db;
        _evidencias         = evidencias;
        _email              = email;
        _logger             = logger;
        _config             = config;
        _httpContextAccessor = httpContextAccessor;
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/recepcion/{id}
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("{id:guid}")]
    public async Task<ActionResult<ApiResponse<EntradaCamionDto>>> Obtener(Guid id)
    {
        var entrada = await _db.ObtenerEntradaPorIdAsync(id);
        if (entrada is null)
            return NotFound(ApiResponse<EntradaCamionDto>.Fail($"No se encontró la entrada con ID {id}."));

        return Ok(ApiResponse<EntradaCamionDto>.Ok(entrada));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/recepcion/suplidores?q=...
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("suplidores")]
    public async Task<ActionResult<ApiResponse<List<SuplidorDto>>>> BuscarSuplidores([FromQuery] string q)
    {
        if (string.IsNullOrWhiteSpace(q)) return Ok(ApiResponse<List<SuplidorDto>>.Ok(new List<SuplidorDto>()));
        var lista = await _db.BuscarSuplidoresAsync(q);
        return Ok(ApiResponse<List<SuplidorDto>>.Ok(lista));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/recepcion/almacenes
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("almacenes")]
    public async Task<ActionResult<ApiResponse<List<AlmacenDto>>>> ListarAlmacenes()
    {
        var usuario = User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value
                      ?? User.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value;
        var lista = await _db.ListarAlmacenesAsync(usuario?.Trim());
        return Ok(ApiResponse<List<AlmacenDto>>.Ok(lista));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // PUT /api/recepcion/{id}/confirmar
    // El almacenista confirma la recepción. Puede incluir evidencias directamente.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpPut("{id:guid}/confirmar")]
    public async Task<ActionResult<ApiResponse<object>>> ConfirmarRecepcion(
        Guid id, [FromBody] ConfirmarRecepcionRequest req)
    {
        if (req.IdEntradaCamion != id)
            return BadRequest(ApiResponse<object>.Fail("El ID en la ruta y en el cuerpo no coinciden."));

        // Validar 9 campos (los capturados en puerta ya están, validamos los de recepción/ajustes)
        if (string.IsNullOrWhiteSpace(req.Conduce) || req.Conduce.Length < 4)
            return BadRequest(ApiResponse<object>.Fail("El Número de Conduce del Agregado es obligatorio y debe tener al menos 4 caracteres."));
        if (string.IsNullOrWhiteSpace(req.ConduceTransporte) || req.ConduceTransporte.Length < 4)
            return BadRequest(ApiResponse<object>.Fail("El Número de Conduce del Transporte es obligatorio y debe tener al menos 4 caracteres."));
        if (string.IsNullOrWhiteSpace(req.IdSuplidor))
            return BadRequest(ApiResponse<object>.Fail("El Suplidor del Agregado es obligatorio."));
        if (string.IsNullOrWhiteSpace(req.IdAlmacen))
            return BadRequest(ApiResponse<object>.Fail("El Almacén de destino es obligatorio."));
        if (req.CantidadRecibida <= 0)
            return BadRequest(ApiResponse<object>.Fail("La cantidad recibida debe ser mayor a 0."));

        var entrada = await _db.ObtenerEntradaPorIdAsync(id);
        if (entrada is null)
            return NotFound(ApiResponse<object>.Fail($"Entrada {id} no encontrada."));

        if (entrada.Status == "CERRADO" || entrada.Status == "BLOQUEADO")
            return Conflict(ApiResponse<object>.Fail(
                $"La entrada está en estado '{entrada.Status}' y no puede modificarse."));

        var usuario = ObtenerUsuario();
        var ip      = _httpContextAccessor.HttpContext?.Connection.RemoteIpAddress?.ToString();

        // 1. Guardar evidencias si vienen incluidas
        Guid idEvidencia = entrada.IdEvidencia ?? Guid.NewGuid();
        bool tieneEvidencia = !string.IsNullOrEmpty(req.FotoConduceBase64)
                           || !string.IsNullOrEmpty(req.FirmaDigitalBase64)
                           || !string.IsNullOrEmpty(req.ImagenFirmadaBase64);

        if (tieneEvidencia && entrada.IdEvidencia is null)
        {
            var metadatos = new
            {
                conduce      = req.Conduce,
                placa        = entrada.Placa,
                transportista = entrada.Transportista,
                chofer       = entrada.NombreChofer
            };

            idEvidencia = await _evidencias.GuardarEvidenciaAsync(
                idRefExterna:       id,
                referencia:         req.Conduce,
                fotoConduceBase64:  req.FotoConduceBase64,
                fotoConduceMime:    req.FotoConduceMime ?? "image/jpeg",
                fotoConduceNombre:  req.FotoConduceNombre,
                firmaDigitalBase64: req.FirmaDigitalBase64,
                imagenFirmadaBase64: req.ImagenFirmadaBase64,
                fotoCamionBase64:   req.FotoCamionBase64,
                metadatos:          metadatos,
                usuario:            usuario,
                ip:                 ip);
        }

        try
        {
            // 2. Confirmar recepción en BD ERP
            var ok = await _db.ConfirmarRecepcionAsync(
                idEntradaCamion:  id,
                fechaRecepcion:   DateTime.Now,
                usuarioRecepcion: usuario,
                idEvidencia:      idEvidencia,
                req:              req);

            if (!ok)
                return StatusCode(500, ApiResponse<object>.Fail("No se pudo actualizar la recepción. Intente nuevamente."));

            return Ok(ApiResponse<object>.Ok(
                new { idEntradaCamion = id, idEvidencia },
                "Recepción confirmada correctamente."));
        }
        catch (InvalidOperationException ex)
        {
            return BadRequest(ApiResponse<object>.Fail(ex.Message));
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/recepcion/{id}/evidencia
    // Guarda o actualiza evidencias (foto conduce, firma, imagen firmada) sin
    // cambiar el status de la recepción. Permite agregar firma posterior.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpPost("{id:guid}/evidencia")]
    public async Task<ActionResult<ApiResponse<object>>> GuardarEvidencia(
        Guid id, [FromBody] ConfirmarRecepcionRequest req)
    {
        var entrada = await _db.ObtenerEntradaPorIdAsync(id);
        if (entrada is null)
            return NotFound(ApiResponse<object>.Fail($"Entrada {id} no encontrada."));

        var usuario = ObtenerUsuario();
        var ip      = _httpContextAccessor.HttpContext?.Connection.RemoteIpAddress?.ToString();

        var metadatos = new
        {
            conduce       = entrada.Conduce,
            placa         = entrada.Placa,
            transportista = entrada.Transportista,
            chofer        = entrada.NombreChofer
        };

        var idEvidencia = await _evidencias.GuardarEvidenciaAsync(
            idRefExterna:        id,
            referencia:          entrada.Conduce,
            fotoConduceBase64:   req.FotoConduceBase64,
            fotoConduceMime:     req.FotoConduceMime,
            fotoConduceNombre:   req.FotoConduceNombre,
            firmaDigitalBase64:  req.FirmaDigitalBase64,
            imagenFirmadaBase64: req.ImagenFirmadaBase64,
            fotoCamionBase64:    req.FotoCamionBase64,
            metadatos:           metadatos,
            usuario:             usuario,
            ip:                  ip);

        return Ok(ApiResponse<object>.Ok(new { idEvidencia }, "Evidencias guardadas correctamente."));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/recepcion/{id}/notificar
    // Envía email con la imagen firmada al transportista y CC configurados.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpPost("{id:guid}/notificar")]
    public async Task<ActionResult<ApiResponse<object>>> Notificar(Guid id, [FromBody] NotificarRequest req)
    {
        var entrada = await _db.ObtenerEntradaPorIdAsync(id);
        if (entrada is null)
            return NotFound(ApiResponse<object>.Fail($"Entrada {id} no encontrada."));

        // Obtener imagen firmada si existe
        byte[]? imagenFirmada = null;
        if (entrada.IdEvidencia.HasValue)
        {
            var (_, _, firmada, _) = await _evidencias.ObtenerBinariosAsync(entrada.IdEvidencia.Value);
            imagenFirmada = firmada;
        }

        // Destinatarios CC desde configuración
        var ccConfig = _config["ControlPuerta:NotificacionCC"] ?? "";
        var cc = ccConfig.Split(';', StringSplitOptions.RemoveEmptyEntries)
            .Concat(req.EmailsCC ?? Array.Empty<string>())
            .ToArray();

        var asunto  = $"Recepción de Conduce #{entrada.Conduce} — {entrada.Transportista}";
        var cuerpo  = GenerarCuerpoEmail(entrada);
        var destino = req.EmailDestinatario ?? "";

        bool enviado = await _email.EnviarConduceFirmadoAsync(
            destinatario:  destino,
            cc:            cc,
            asunto:        asunto,
            cuerpoHtml:    cuerpo,
            adjunto:       imagenFirmada,
            nombreAdjunto: $"Conduce_{entrada.Conduce}_Firmado.jpg");

        if (!enviado)
            return StatusCode(500, ApiResponse<object>.Fail("No se pudo enviar el correo. Verifique configuración SMTP."));

        return Ok(ApiResponse<object>.Ok(
            new { enviado = true },
            $"Correo enviado correctamente a {destino}."));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/recepcion/{id}/ticket
    // Retorna los datos estructurados para el ticket imprimible.
    // El frontend genera el PDF con jsPDF.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("{id:guid}/ticket")]
    public async Task<ActionResult<ApiResponse<TicketDto>>> ObtenerTicket(Guid id)
    {
        var entrada = await _db.ObtenerEntradaPorIdAsync(id);
        if (entrada is null)
            return NotFound(ApiResponse<TicketDto>.Fail($"Entrada {id} no encontrada."));

        var ticket = new TicketDto
        {
            IdEntradaCamion  = entrada.IdEntradaCamion,
            Conduce          = entrada.Conduce,
            Placa            = entrada.Placa,
            Transportista    = entrada.Transportista ?? "",
            NombreChofer     = entrada.NombreChofer ?? "",
            Producto         = entrada.Producto ?? "",
            FechaEntrada     = entrada.FechaEntrada,
            FechaRecepcion   = entrada.FechaRecepcion,
            UsuarioRecepcion = entrada.UsuarioRecepcion ?? "",
            Status           = entrada.Status,
            OrdenNumero      = entrada.OrdenNumero,
            FechaImpresion   = DateTime.Now
        };

        return Ok(ApiResponse<TicketDto>.Ok(ticket));
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/recepcion/{id}/evidencia/{tipo}
    // Descarga una imagen binaria. tipo = foto | firma | firmada | camion
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("{id:guid}/evidencia/{tipo}")]
    public async Task<IActionResult> DescargarEvidencia(Guid id, string tipo)
    {
        var entrada = await _db.ObtenerEntradaPorIdAsync(id);
        if (entrada?.IdEvidencia is null)
            return NotFound("No hay evidencias para esta entrada.");

        var (foto, firma, firmada, camion) = await _evidencias.ObtenerBinariosAsync(entrada.IdEvidencia.Value);

        var (bytes, mime, nombre) = tipo.ToLower() switch
        {
            "foto"    => (foto,    "image/jpeg", $"foto_{entrada.Conduce}.jpg"),
            "firma"   => (firma,   "image/png",  $"firma_{entrada.Conduce}.png"),
            "firmada" => (firmada, "image/jpeg", $"firmado_{entrada.Conduce}.jpg"),
            "camion"  => (camion,  "image/jpeg", $"camion_{entrada.Conduce}.jpg"),
            _         => (null, "", "")
        };

        if (bytes is null)
            return NotFound($"No hay imagen de tipo '{tipo}' para esta entrada.");

        return File(bytes, mime, nombre);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private string ObtenerUsuario()
        => User.FindFirst(ClaimTypes.Name)?.Value
        ?? User.FindFirst("sub")?.Value
        ?? User.FindFirst("idSegUserGrp")?.Value
        ?? "SISTEMA";

    private static string GenerarCuerpoEmail(EntradaCamionDto e)
    {
        var sb = new StringBuilder();
        sb.AppendLine("<!DOCTYPE html><html><body style='font-family:Arial,sans-serif;max-width:600px;margin:0 auto;'>");
        sb.AppendLine("<div style='background:#1e40af;color:white;padding:20px;border-radius:8px 8px 0 0;'>");
        sb.AppendLine("<h2 style='margin:0;'>✅ Confirmación de Recepción de Conduce</h2>");
        sb.AppendLine("</div>");
        sb.AppendLine("<div style='background:#f8fafc;padding:24px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;'>");
        sb.AppendLine("<table style='width:100%;border-collapse:collapse;'>");
        void fila(string label, string val)
        {
            sb.AppendLine($"<tr><td style='padding:8px;font-weight:bold;color:#64748b;width:40%;'>{label}</td>");
            sb.AppendLine($"<td style='padding:8px;color:#1e293b;'>{val}</td></tr>");
        }
        fila("# Conduce",       e.Conduce);
        fila("Placa",           e.Placa);
        fila("Transportista",   e.Transportista ?? "-");
        fila("Chofer",          e.NombreChofer ?? "-");
        fila("Producto",        e.Producto ?? "-");
        fila("Fecha Entrada",   e.FechaEntrada.ToString("dd/MM/yyyy HH:mm"));
        fila("Fecha Recepción", e.FechaRecepcion?.ToString("dd/MM/yyyy HH:mm") ?? "-");
        fila("Almacenista",     e.UsuarioRecepcion ?? "-");
        fila("OC Asignada",     e.OrdenNumero?.ToString() ?? "Pendiente");
        sb.AppendLine("</table>");
        sb.AppendLine("<p style='margin-top:16px;color:#64748b;font-size:12px;'>Este correo fue generado automáticamente por el sistema Control de Puerta — SADE ERP. Por favor, adjunte este correo a sus documentos de gestión de cobro.</p>");
        sb.AppendLine("</div></body></html>");
        return sb.ToString();
    }
}

// ── DTOs adicionales de este controlador ─────────────────────────────────────

public record NotificarRequest
{
    public string   EmailDestinatario { get; init; } = "";
    public string[]? EmailsCC        { get; init; }
}

public record TicketDto
{
    public Guid      IdEntradaCamion   { get; init; }
    public string    Conduce           { get; init; } = "";
    public string    Placa             { get; init; } = "";
    public string    Transportista     { get; init; } = "";
    public string    NombreChofer      { get; init; } = "";
    public string    Producto          { get; init; } = "";
    public DateTime  FechaEntrada      { get; init; }
    public DateTime? FechaRecepcion    { get; init; }
    public string    UsuarioRecepcion  { get; init; } = "";
    public string    Status            { get; init; } = "";
    public int?      OrdenNumero       { get; init; }
    public DateTime  FechaImpresion    { get; init; }
}
