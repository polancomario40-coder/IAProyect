using Microsoft.Data.SqlClient;
using System.Collections.Concurrent;
using System.Security.Claims;

namespace ControlPuertaAPI.Services;

/// <summary>
/// Fábrica de conexiones multi-empresa para el ERP y evidencias.
/// Resuelve dinámicamente la base de datos según la empresa seleccionada en el SSO (auth-center),
/// consultando el catálogo cfgEmpresa de cbsrepository.
/// </summary>
public interface IConnectionFactory
{
    SqlConnection CreateErpConnection();
    SqlConnection CreateEvidenciasConnection();
    string GetCurrentDatabaseName();
}

public class ConnectionFactory : IConnectionFactory
{
    private readonly IConfiguration _config;
    private readonly IHttpContextAccessor _httpContextAccessor;
    private readonly ILogger<ConnectionFactory> _logger;
    private readonly string _defaultErpConnStr;
    private readonly string _evidenciasConnStr;
    private readonly string _cbsRepoConnStr;

    // Caché thread-safe de idEmpresa -> BaseDatos
    private static readonly ConcurrentDictionary<string, string> _dbCache = new(StringComparer.OrdinalIgnoreCase);

    public ConnectionFactory(
        IConfiguration config, 
        IHttpContextAccessor httpContextAccessor,
        ILogger<ConnectionFactory> logger)
    {
        _config = config;
        _httpContextAccessor = httpContextAccessor;
        _logger = logger;

        _defaultErpConnStr = config.GetConnectionString("ErpConnection")
            ?? throw new InvalidOperationException("ConnectionStrings:ErpConnection no configurada.");
        _evidenciasConnStr = config.GetConnectionString("EvidenciasConnection")
            ?? throw new InvalidOperationException("ConnectionStrings:EvidenciasConnection no configurada.");

        // Cadena para consultar el catálogo de empresas en cbsrepository
        var builder = new SqlConnectionStringBuilder(_defaultErpConnStr)
        {
            InitialCatalog = "cbsrepository"
        };
        _cbsRepoConnStr = builder.ConnectionString;
    }

    public SqlConnection CreateErpConnection()
    {
        var connStr = ResolveErpConnectionString();
        return new SqlConnection(connStr);
    }

    public SqlConnection CreateEvidenciasConnection() => new(_evidenciasConnStr);

    public string GetCurrentDatabaseName()
    {
        var connStr = ResolveErpConnectionString();
        var builder = new SqlConnectionStringBuilder(connStr);
        return builder.InitialCatalog;
    }

    private string ResolveErpConnectionString()
    {
        var httpContext = _httpContextAccessor.HttpContext;
        if (httpContext == null)
            return _defaultErpConnStr;

        // 1. Obtener idEmpresa del header X-Selected-Company, query param o JWT claims
        var idEmpresa = httpContext.Request.Headers["X-Selected-Company"].FirstOrDefault();
        if (string.IsNullOrWhiteSpace(idEmpresa))
            idEmpresa = httpContext.Request.Query["idEmpresa"].FirstOrDefault();
        if (string.IsNullOrWhiteSpace(idEmpresa))
            idEmpresa = httpContext.Request.Query["empresaId"].FirstOrDefault();
        if (string.IsNullOrWhiteSpace(idEmpresa))
            idEmpresa = httpContext.User.FindFirst("idEmpresa")?.Value 
                     ?? httpContext.User.FindFirst("empresaId")?.Value;

        if (string.IsNullOrWhiteSpace(idEmpresa))
            return _defaultErpConnStr;

        idEmpresa = idEmpresa.Trim();

        // 2. Verificar si ya está en caché
        if (_dbCache.TryGetValue(idEmpresa, out var cachedDb) && !string.IsNullOrWhiteSpace(cachedDb))
        {
            return BuildConnectionString(cachedDb);
        }

        // 3. Consultar cbsrepository.dbo.cfgEmpresa
        try
        {
            using var repoConn = new SqlConnection(_cbsRepoConnStr);
            repoConn.Open();
            using var cmd = repoConn.CreateCommand();
            cmd.CommandText = @"
                SELECT TOP 1 BaseDatos 
                FROM cfgEmpresa 
                WHERE CAST(idEmpresa AS VARCHAR(50)) = @id 
                   OR Empresa = @id";
            cmd.Parameters.AddWithValue("@id", idEmpresa);

            var dbResult = cmd.ExecuteScalar()?.ToString()?.Trim();
            if (!string.IsNullOrWhiteSpace(dbResult))
            {
                _dbCache[idEmpresa] = dbResult;
                _logger.LogInformation("[TENANT] Empresa '{IdEmpresa}' resuelta dinámicamente a Base de Datos: '{Db}'", idEmpresa, dbResult);
                return BuildConnectionString(dbResult);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "[TENANT] Error al resolver empresa '{IdEmpresa}' desde cfgEmpresa", idEmpresa);
        }

        return _defaultErpConnStr;
    }

    private string BuildConnectionString(string databaseName)
    {
        var builder = new SqlConnectionStringBuilder(_defaultErpConnStr)
        {
            InitialCatalog = databaseName
        };
        return builder.ConnectionString;
    }
}
