using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using ControlPuertaAPI.Models;

namespace ControlPuertaAPI.Services;

/// <summary>
/// Servicio de OCR usando Azure AI Document Intelligence.
/// La clave y endpoint se leen de la configuración —nunca hardcodeados—
/// para que cada cliente configure sus propias credenciales.
/// </summary>
public interface IOcrService
{
    Task<OcrPlacaResponse> ExtraerTextoPlacaAsync(string imagenBase64, string mimeType);
}

public class OcrService : IOcrService
{
    private readonly IConfiguration _config;
    private readonly ILogger<OcrService> _logger;
    private readonly HttpClient _httpClient;

    public OcrService(IConfiguration config, ILogger<OcrService> logger, IHttpClientFactory httpClientFactory)
    {
        _config     = config;
        _logger     = logger;
        _httpClient = httpClientFactory.CreateClient("AzureDocIntelligence");
    }

    public async Task<OcrPlacaResponse> ExtraerTextoPlacaAsync(string imagenBase64, string mimeType)
    {
        var endpoint = _config["AzureDocumentIntelligence:Endpoint"];
        var apiKey   = _config["AzureDocumentIntelligence:ApiKey"];
        var modelId  = _config["AzureDocumentIntelligence:ModelId"] ?? "prebuilt-read";

        // ── Modo fallback: si no hay clave configurada, simular respuesta ──────
        if (string.IsNullOrWhiteSpace(apiKey) ||
            apiKey.Contains("YOUR_AZURE", StringComparison.OrdinalIgnoreCase) ||
            string.IsNullOrWhiteSpace(endpoint))
        {
            _logger.LogWarning("[OCR] Azure AI Document Intelligence no configurado. Retornando respuesta simulada para desarrollo.");
            return new OcrPlacaResponse(
                Exito: false,
                TextoDetectado: "",
                Confianza: 0.0m,
                Mensaje: "⚠ Modo simulado: Configure AzureDocumentIntelligence:ApiKey en appsettings."
            );
        }

        try
        {
            // ── Preparar imagen como bytes ───────────────────────────────────
            var imageBytes = Convert.FromBase64String(imagenBase64);

            var apiVersion = _config["AzureDocumentIntelligence:ApiVersion"] ?? "2024-11-30";
            var analyzeUrl = $"{endpoint.TrimEnd('/')}/documentintelligence/documentModels/{modelId}:analyze?api-version={apiVersion}";

            using var content = new ByteArrayContent(imageBytes);
            content.Headers.ContentType = new MediaTypeHeaderValue(mimeType);
            _httpClient.DefaultRequestHeaders.Remove("Ocp-Apim-Subscription-Key");
            _httpClient.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", apiKey);

            var submitResponse = await _httpClient.PostAsync(analyzeUrl, content);

            // Fallback a versión 2023-07-31 si la versión configurada devuelve 410 (Gone) o 404
            if (submitResponse.StatusCode == System.Net.HttpStatusCode.Gone || 
                submitResponse.StatusCode == System.Net.HttpStatusCode.NotFound)
            {
                var fallbackUrl = $"{endpoint.TrimEnd('/')}/formrecognizer/documentModels/{modelId}:analyze?api-version=2023-07-31";
                using var fallbackContent = new ByteArrayContent(imageBytes);
                fallbackContent.Headers.ContentType = new MediaTypeHeaderValue(mimeType);
                var fallbackResp = await _httpClient.PostAsync(fallbackUrl, fallbackContent);
                if (fallbackResp.IsSuccessStatusCode)
                {
                    submitResponse = fallbackResp;
                }
            }

            if (!submitResponse.IsSuccessStatusCode)
            {
                var errBody = await submitResponse.Content.ReadAsStringAsync();
                _logger.LogWarning("[OCR] Azure returned {StatusCode}: {Error}", submitResponse.StatusCode, errBody);
                return new OcrPlacaResponse(
                    Exito: false,
                    TextoDetectado: "",
                    Confianza: 0m,
                    Mensaje: "No se pudo detectar el texto automáticamente. Ingréselo manualmente."
                );
            }

            // La URL de resultado viene en el header Operation-Location
            var operationLocation = submitResponse.Headers.GetValues("Operation-Location").FirstOrDefault();
            if (string.IsNullOrWhiteSpace(operationLocation))
            {
                return new OcrPlacaResponse(false, "", 0m, "Azure no retornó Operation-Location.");
            }

            // ── Llamada 2: Polling hasta que el análisis complete ────────────
            string? resultJson = null;
            for (int i = 0; i < 15; i++)  // máx ~30 segundos
            {
                await Task.Delay(2000);
                var pollResponse = await _httpClient.GetAsync(operationLocation);
                resultJson = await pollResponse.Content.ReadAsStringAsync();

                using var doc = JsonDocument.Parse(resultJson);
                var status = doc.RootElement.GetProperty("status").GetString();

                if (status == "succeeded") break;
                if (status == "failed")
                {
                    _logger.LogWarning("[OCR] Azure status failed: {Result}", resultJson);
                    return new OcrPlacaResponse(false, "", 0m, "No se pudo analizar la imagen.");
                }
            }

            if (resultJson is null)
                return new OcrPlacaResponse(false, "", 0m, "Tiempo de espera agotado esperando análisis.");

            // ── Parsear resultado ────────────────────────────────────────────
            return ParsearResultadoAzure(resultJson);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "[OCR] Error llamando Azure Document Intelligence");
            return new OcrPlacaResponse(
                Exito: false,
                TextoDetectado: "",
                Confianza: 0m,
                Mensaje: "No se pudo detectar el texto automáticamente. Ingréselo manualmente."
            );
        }
    }

    private static OcrPlacaResponse ParsearResultadoAzure(string json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;

        if (!root.TryGetProperty("analyzeResult", out var analyzeResult))
            return new OcrPlacaResponse(false, "", 0m, "Respuesta de Azure sin analyzeResult.");

        // Recopilar todos los bloques de texto
        var sb = new StringBuilder();
        double totalConfianza = 0;
        int    contadorPalabras = 0;

        if (analyzeResult.TryGetProperty("pages", out var pages))
        {
            foreach (var page in pages.EnumerateArray())
            {
                if (!page.TryGetProperty("words", out var words)) continue;
                foreach (var word in words.EnumerateArray())
                {
                    var content    = word.GetProperty("content").GetString() ?? "";
                    var confidence = word.TryGetProperty("confidence", out var c) ? c.GetDouble() : 0.9;

                    sb.Append(content).Append(' ');
                    totalConfianza += confidence;
                    contadorPalabras++;
                }
            }
        }

        var textoCompleto = sb.ToString().Trim().ToUpperInvariant();
        var confianza     = contadorPalabras > 0 ? (decimal)(totalConfianza / contadorPalabras) : 0m;

        // Extraer texto de placa: eliminar caracteres no alfanuméricos
        var textoPlaca = new string(textoCompleto.Where(c => char.IsLetterOrDigit(c) || c == '-').ToArray());

        return new OcrPlacaResponse(
            Exito: !string.IsNullOrEmpty(textoPlaca),
            TextoDetectado: textoPlaca,
            Confianza: Math.Round(confianza, 4),
            Mensaje: null
        );
    }
}
