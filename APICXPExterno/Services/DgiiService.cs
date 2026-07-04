using System.Net.Http;
using System.Text.Json;

namespace CxpApi.Services
{
    public class DgiiService
    {
        private readonly HttpClient _httpClient;
        private readonly IConfiguration _configuration;
        private readonly ILogger<DgiiService> _logger;

        public DgiiService(HttpClient httpClient, IConfiguration configuration, ILogger<DgiiService> logger)
        {
            _httpClient = httpClient;
            _configuration = configuration;
            _logger = logger;
        }

        public async Task<DgiiResponse?> ConsultarRncAsync(string rnc)
        {
            try
            {
                var apiUrl = _configuration.GetValue<string>("DgiiApiUrl");
                if (string.IsNullOrEmpty(apiUrl))
                {
                    _logger.LogWarning("DgiiApiUrl no está configurada en appsettings.json");
                    return null;
                }

                // Asegurar que la URL termine en "/" y añadir el rnc
                if (!apiUrl.EndsWith("/")) apiUrl += "/";
                var url = $"{apiUrl}{rnc}";

                var response = await _httpClient.GetAsync(url);
                if (response.IsSuccessStatusCode)
                {
                    var content = await response.Content.ReadAsStringAsync();
                    
                    // Asumiremos un formato genérico que tiene RazonSocial o NombreComercial
                    var jsonDoc = JsonDocument.Parse(content);
                    var root = jsonDoc.RootElement;
                    
                    string nombre = "";
                    if (root.TryGetProperty("RazonSocial", out var razonSocialProp))
                    {
                        nombre = razonSocialProp.GetString() ?? "";
                    }
                    else if (root.TryGetProperty("nombre", out var nombreProp))
                    {
                        nombre = nombreProp.GetString() ?? "";
                    }
                    else if (root.TryGetProperty("NombreComercial", out var nombreComercialProp))
                    {
                        nombre = nombreComercialProp.GetString() ?? "";
                    }

                    if (!string.IsNullOrEmpty(nombre))
                    {
                        return new DgiiResponse { Encontrado = true, NombreComercial = nombre };
                    }
                }
                return null;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error consultando DGII para el RNC {rnc}");
                return null;
            }
        }
    }

    public class DgiiResponse
    {
        public bool Encontrado { get; set; }
        public string? NombreComercial { get; set; }
    }
}
