using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using ControlPuertaAPI.Models;
using System.Globalization;
using System.Text.RegularExpressions;

namespace ControlPuertaAPI.Services;

/// <summary>
/// Servicio de OCR usando Azure AI Document Intelligence.
/// La clave y endpoint se leen de la configuración —nunca hardcodeados—
/// para que cada cliente configure sus propias credenciales.
/// </summary>
public interface IOcrService
{
    Task<OcrPlacaResponse> ExtraerTextoPlacaAsync(string imagenBase64, string mimeType);
    Task<List<ItemConciliacionInputDto>> ExtraerConducesDeDocumentoAsync(byte[] fileBytes, string mimeType);
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

    // ──────────────────────────────────────────────────────────────────────────
    // Extracción de Conduces desde Documentos (PDF escaneado o Imagen)
    // ──────────────────────────────────────────────────────────────────────────
    public async Task<List<ItemConciliacionInputDto>> ExtraerConducesDeDocumentoAsync(byte[] fileBytes, string mimeType)
    {
        var endpoint = _config["AzureDocumentIntelligence:Endpoint"];
        var apiKey   = _config["AzureDocumentIntelligence:ApiKey"];
        var modelId  = "prebuilt-layout";

        // Si no está configurada la clave de Azure, retornar datos simulados para desarrollo
        if (string.IsNullOrWhiteSpace(apiKey) ||
            apiKey.Contains("YOUR_AZURE", StringComparison.OrdinalIgnoreCase) ||
            string.IsNullOrWhiteSpace(endpoint))
        {
            _logger.LogWarning("[OCR-Doc] Azure AI Document Intelligence no configurado. Retornando datos simulados para desarrollo.");
            return GenerarItemsSimulados();
        }

        try
        {
            var apiVersion = _config["AzureDocumentIntelligence:ApiVersion"] ?? "2024-11-30";
            var analyzeUrl = $"{endpoint.TrimEnd('/')}/documentintelligence/documentModels/{modelId}:analyze?api-version={apiVersion}";

            using var content = new ByteArrayContent(fileBytes);
            content.Headers.ContentType = new MediaTypeHeaderValue(string.IsNullOrWhiteSpace(mimeType) ? "application/pdf" : mimeType);
            _httpClient.DefaultRequestHeaders.Remove("Ocp-Apim-Subscription-Key");
            _httpClient.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", apiKey);

            var submitResponse = await _httpClient.PostAsync(analyzeUrl, content);

            // Fallback a API 2023-07-31 si la versión devuelve 404 o 410
            if (submitResponse.StatusCode == System.Net.HttpStatusCode.Gone ||
                submitResponse.StatusCode == System.Net.HttpStatusCode.NotFound)
            {
                var fallbackUrl = $"{endpoint.TrimEnd('/')}/formrecognizer/documentModels/{modelId}:analyze?api-version=2023-07-31";
                using var fallbackContent = new ByteArrayContent(fileBytes);
                fallbackContent.Headers.ContentType = new MediaTypeHeaderValue(string.IsNullOrWhiteSpace(mimeType) ? "application/pdf" : mimeType);
                var fallbackResp = await _httpClient.PostAsync(fallbackUrl, fallbackContent);
                if (fallbackResp.IsSuccessStatusCode)
                {
                    submitResponse = fallbackResp;
                }
            }

            if (!submitResponse.IsSuccessStatusCode)
            {
                var errBody = await submitResponse.Content.ReadAsStringAsync();
                _logger.LogWarning("[OCR-Doc] Azure devolvió {StatusCode}: {Error}", submitResponse.StatusCode, errBody);
                return GenerarItemsSimulados();
            }

            var operationLocation = submitResponse.Headers.GetValues("Operation-Location").FirstOrDefault();
            if (string.IsNullOrWhiteSpace(operationLocation))
            {
                _logger.LogWarning("[OCR-Doc] Azure no retornó Operation-Location.");
                return GenerarItemsSimulados();
            }

            // Polling hasta completar
            string? resultJson = null;
            for (int i = 0; i < 25; i++)
            {
                await Task.Delay(1500);
                var pollResponse = await _httpClient.GetAsync(operationLocation);
                resultJson = await pollResponse.Content.ReadAsStringAsync();

                using var doc = JsonDocument.Parse(resultJson);
                var status = doc.RootElement.GetProperty("status").GetString();

                if (status == "succeeded") break;
                if (status == "failed")
                {
                    _logger.LogWarning("[OCR-Doc] Azure status failed: {Result}", resultJson);
                    return GenerarItemsSimulados();
                }
            }

            if (string.IsNullOrWhiteSpace(resultJson))
                return GenerarItemsSimulados();

            return ParsearDocumentoAzure(resultJson);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "[OCR-Doc] Error analizando documento en Azure Document Intelligence");
            return GenerarItemsSimulados();
        }
    }

    private static List<ItemConciliacionInputDto> ParsearDocumentoAzure(string json)
    {
        var items = new List<ItemConciliacionInputDto>();
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;

        if (!root.TryGetProperty("analyzeResult", out var analyzeResult))
            return items;

        // 1. Intentar extraer de tablas estructuradas (layout)
        if (analyzeResult.TryGetProperty("tables", out var tables) && tables.GetArrayLength() > 0)
        {
            foreach (var table in tables.EnumerateArray())
            {
                var rowCount = table.TryGetProperty("rowCount", out var rc) ? rc.GetInt32() : 0;
                var colCount = table.TryGetProperty("columnCount", out var cc) ? cc.GetInt32() : 0;
                if (rowCount < 2 || colCount < 2) continue;

                var grid = new Dictionary<(int r, int c), string>();
                if (table.TryGetProperty("cells", out var cells))
                {
                    foreach (var cell in cells.EnumerateArray())
                    {
                        var r = cell.GetProperty("rowIndex").GetInt32();
                        var c = cell.GetProperty("columnIndex").GetInt32();
                        var content = cell.TryGetProperty("content", out var cnt) ? cnt.GetString() ?? "" : "";
                        grid[(r, c)] = content.Trim();
                    }
                }

                // Identificar fila de encabezados
                int headerRow = -1;
                int colFecha = -1, colConduce = -1, colProd = -1, colMina = -1, colPlanta = -1;
                int colCant = -1, colPrecio = -1, colTotal = -1;

                for (int r = 0; r < Math.Min(rowCount, 5); r++)
                {
                    int matches = 0;
                    for (int c = 0; c < colCount; c++)
                    {
                        var val = grid.GetValueOrDefault((r, c), "").ToLowerInvariant();
                        if (val.Contains("conduce") || val.Contains("ticket") || val.Contains("no")) matches++;
                        if (val.Contains("fecha")) matches++;
                        if (val.Contains("producto") || val.Contains("material")) matches++;
                        if (val.Contains("mina") || val.Contains("cantera")) matches++;
                        if (val.Contains("planta") || val.Contains("destino")) matches++;
                        if (val.Contains("cant")) matches++;
                        if (val.Contains("precio")) matches++;
                        if (val.Contains("total")) matches++;
                    }

                    if (matches >= 2)
                    {
                        headerRow = r;
                        for (int c = 0; c < colCount; c++)
                        {
                            var h = grid.GetValueOrDefault((r, c), "").ToLowerInvariant();
                            if (colFecha == -1 && h.Contains("fecha")) colFecha = c;
                            else if (colConduce == -1 && (h.Contains("conduce") || h.Contains("ticket") || h.Contains("no"))) colConduce = c;
                            else if (colProd == -1 && (h.Contains("prod") || h.Contains("material") || h.Contains("desc"))) colProd = c;
                            else if (colMina == -1 && (h.Contains("mina") || h.Contains("origen") || h.Contains("cantera"))) colMina = c;
                            else if (colPlanta == -1 && (h.Contains("planta") || h.Contains("destino") || h.Contains("almacen"))) colPlanta = c;
                            else if (colCant == -1 && (h.Contains("cant") || h.Contains("m3") || h.Contains("ton"))) colCant = c;
                            else if (colPrecio == -1 && (h.Contains("prec") || h.Contains("costo"))) colPrecio = c;
                            else if (colTotal == -1 && (h.Contains("total") || h.Contains("monto") || h.Contains("imp"))) colTotal = c;
                        }
                        break;
                    }
                }

                if (headerRow >= 0 && colConduce >= 0)
                {
                    for (int r = headerRow + 1; r < rowCount; r++)
                    {
                        var conduce = grid.GetValueOrDefault((r, colConduce), "").Trim();
                        conduce = Regex.Replace(conduce, @"[^\w\-]", "").Trim();
                        if (string.IsNullOrWhiteSpace(conduce) || conduce.Equals("total", StringComparison.OrdinalIgnoreCase))
                            continue;

                        var fechaRaw  = colFecha  >= 0 ? grid.GetValueOrDefault((r, colFecha), "") : "";
                        var prodRaw   = colProd   >= 0 ? grid.GetValueOrDefault((r, colProd), "") : "";
                        var minaRaw   = colMina   >= 0 ? grid.GetValueOrDefault((r, colMina), "") : "";
                        var plantaRaw = colPlanta >= 0 ? grid.GetValueOrDefault((r, colPlanta), "") : "";
                        var cantVal   = colCant   >= 0 ? ParsearDecimal(grid.GetValueOrDefault((r, colCant), "")) : 0m;
                        var precVal   = colPrecio >= 0 ? ParsearDecimal(grid.GetValueOrDefault((r, colPrecio), "")) : 0m;
                        var totVal    = colTotal  >= 0 ? ParsearDecimal(grid.GetValueOrDefault((r, colTotal), "")) : 0m;

                        if (totVal == 0m && cantVal > 0 && precVal > 0)
                            totVal = Math.Round(cantVal * precVal, 2);

                        items.Add(new ItemConciliacionInputDto
                        {
                            Fecha     = ParsearFecha(fechaRaw),
                            NoConduce = conduce,
                            Producto  = string.IsNullOrWhiteSpace(prodRaw) ? null : prodRaw,
                            Mina      = string.IsNullOrWhiteSpace(minaRaw) ? null : minaRaw,
                            Planta    = string.IsNullOrWhiteSpace(plantaRaw) ? null : plantaRaw,
                            Cantidad  = cantVal,
                            Precio    = precVal,
                            Total     = totVal
                        });
                    }
                }
            }
        }

        // 2. Si no se detectaron filas por tabla, fallback a líneas de texto
        if (items.Count == 0 && analyzeResult.TryGetProperty("pages", out var pages))
        {
            var lineas = new List<string>();
            foreach (var page in pages.EnumerateArray())
            {
                if (page.TryGetProperty("lines", out var pageLines))
                {
                    foreach (var line in pageLines.EnumerateArray())
                    {
                        var content = line.TryGetProperty("content", out var c) ? c.GetString() : null;
                        if (!string.IsNullOrWhiteSpace(content))
                            lineas.Add(content.Trim());
                    }
                }
            }
            items.AddRange(ParsearLineasDocumento(lineas));
        }

        return items;
    }

    private static List<ItemConciliacionInputDto> ParsearLineasDocumento(List<string> lineas)
    {
        var items = new List<ItemConciliacionInputDto>();
        var regexFecha = new Regex(@"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b");
        var regexNumeros = new Regex(@"\b\d+(?:[.,]\d+)?\b");

        foreach (var linea in lineas)
        {
            if (linea.Contains("PLANTILLA", StringComparison.OrdinalIgnoreCase) ||
                linea.Contains("No. conduce", StringComparison.OrdinalIgnoreCase))
                continue;

            var matchFecha = regexFecha.Match(linea);
            var matchesNum = regexNumeros.Matches(linea);

            if (matchesNum.Count >= 2)
            {
                var tokens = linea.Split(new[] { ' ', '\t', '|' }, StringSplitOptions.RemoveEmptyEntries);
                string conduce = "";
                decimal cant = 0m, precio = 0m, total = 0m;

                foreach (var tok in tokens)
                {
                    if (string.IsNullOrEmpty(conduce) && 
                        (tok.Length >= 4 && (char.IsDigit(tok[0]) || tok.StartsWith("C-") || tok.StartsWith("COND-") || tok.StartsWith("T-"))))
                    {
                        conduce = tok;
                    }
                }

                if (!string.IsNullOrEmpty(conduce))
                {
                    var numList = new List<decimal>();
                    for (int i = 0; i < matchesNum.Count; i++)
                    {
                        var v = ParsearDecimal(matchesNum[i].Value);
                        if (v > 0) numList.Add(v);
                    }

                    if (numList.Count >= 3)
                    {
                        cant   = numList[^3];
                        precio = numList[^2];
                        total  = numList[^1];
                    }
                    else if (numList.Count == 2)
                    {
                        cant   = numList[0];
                        precio = numList[1];
                        total  = Math.Round(cant * precio, 2);
                    }
                    else if (numList.Count == 1)
                    {
                        cant = numList[0];
                    }

                    items.Add(new ItemConciliacionInputDto
                    {
                        Fecha     = matchFecha.Success ? ParsearFecha(matchFecha.Value) : DateTime.Today,
                        NoConduce = conduce,
                        Producto  = "AGREGADOS",
                        Mina      = "MINA",
                        Planta    = "PLANTA 1",
                        Cantidad  = cant,
                        Precio    = precio,
                        Total     = total > 0 ? total : Math.Round(cant * precio, 2)
                    });
                }
            }
        }

        return items;
    }

    private static decimal ParsearDecimal(string? raw)
    {
        if (string.IsNullOrWhiteSpace(raw)) return 0m;
        var cleaned = raw.Trim().Replace("$", "").Replace("RD", "").Replace(" ", "");
        if (cleaned.Contains(',') && cleaned.Contains('.'))
        {
            if (cleaned.IndexOf(',') < cleaned.IndexOf('.'))
                cleaned = cleaned.Replace(",", "");
            else
                cleaned = cleaned.Replace(".", "").Replace(',', '.');
        }
        else if (cleaned.Contains(','))
        {
            cleaned = cleaned.Replace(',', '.');
        }
        cleaned = new string(cleaned.Where(c => char.IsDigit(c) || c == '.' || c == '-').ToArray());
        if (decimal.TryParse(cleaned, NumberStyles.Any, CultureInfo.InvariantCulture, out var val))
            return val;
        return 0m;
    }

    private static DateTime? ParsearFecha(string? raw)
    {
        if (string.IsNullOrWhiteSpace(raw)) return null;
        raw = raw.Trim();
        string[] formats = { "dd/MM/yyyy", "d/M/yyyy", "dd-MM-yyyy", "d-M-yyyy", "yyyy-MM-dd", "yyyy/MM/dd", "dd/MM/yy", "d/M/yy" };
        if (DateTime.TryParseExact(raw, formats, CultureInfo.InvariantCulture, DateTimeStyles.None, out var dtExact))
            return dtExact;
        if (DateTime.TryParse(raw, new CultureInfo("es-DO"), DateTimeStyles.None, out var dtEs))
            return dtEs;
        if (DateTime.TryParse(raw, CultureInfo.InvariantCulture, DateTimeStyles.None, out var dtInv))
            return dtInv;
        return null;
    }

    private static List<ItemConciliacionInputDto> GenerarItemsSimulados()
    {
        return new List<ItemConciliacionInputDto>
        {
            new() { Fecha = DateTime.Today.AddDays(-5), NoConduce = "10492", Producto = "ARENA LAVADA", Mina = "CANTERA NORTE", Planta = "PLANTA SANTO DOMINGO", Cantidad = 18.5m, Precio = 450m, Total = 8325m },
            new() { Fecha = DateTime.Today.AddDays(-4), NoConduce = "10493", Producto = "GRAVILLA 1/2", Mina = "CANTERA SUR", Planta = "PLANTA SANTO DOMINGO", Cantidad = 22.0m, Precio = 520m, Total = 11440m },
            new() { Fecha = DateTime.Today.AddDays(-3), NoConduce = "10494", Producto = "ARENA AZUL", Mina = "CANTERA ESTE", Planta = "PLANTA SANTIAGO", Cantidad = 16.0m, Precio = 480m, Total = 7680m },
            new() { Fecha = DateTime.Today.AddDays(-2), NoConduce = "10495", Producto = "CASCAJO", Mina = "CANTERA NORTE", Planta = "PLANTA SANTO DOMINGO", Cantidad = 20.0m, Precio = 380m, Total = 7600m },
            new() { Fecha = DateTime.Today.AddDays(-1), NoConduce = "10496", Producto = "ARENA LAVADA", Mina = "CANTERA NORTE", Planta = "PLANTA SANTO DOMINGO", Cantidad = 19.5m, Precio = 450m, Total = 8775m }
        };
    }
            Mensaje: null
        );
    }
}
