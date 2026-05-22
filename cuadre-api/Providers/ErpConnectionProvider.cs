using System;
using System.Linq;
using System.Security.Claims;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Configuration;
using Microsoft.EntityFrameworkCore;
using Microsoft.Data.SqlClient;
using CuadreApi.Data;
using CuadreApi.Models;

namespace CuadreApi.Providers;

public class ErpConnectionProvider : IErpConnectionProvider
{
    private readonly IHttpContextAccessor _httpContextAccessor;
    private readonly IServiceProvider _serviceProvider;
    private readonly IConfiguration _configuration;

    public ErpConnectionProvider(IHttpContextAccessor httpContextAccessor, IServiceProvider serviceProvider, IConfiguration configuration)
    {
        _httpContextAccessor = httpContextAccessor;
        _serviceProvider = serviceProvider;
        _configuration = configuration;
    }

    public string GetConnectionString()
    {
        var httpContext = _httpContextAccessor.HttpContext;
        var selectedCompanyHeader = httpContext?.Request.Headers["X-Selected-Company"].FirstOrDefault();

        // Safe fallback logic: if unauthenticated or header is missing, return the default connection string
        if (httpContext?.User.Identity?.IsAuthenticated != true ||
            string.IsNullOrEmpty(selectedCompanyHeader) || 
            !Guid.TryParse(selectedCompanyHeader, out Guid idEmpresa))
        {
            var defaultConn = _configuration.GetConnectionString("CuadreConnection");
            if (string.IsNullOrEmpty(defaultConn))
            {
                defaultConn = "Server=localhost;Database=SADEEstandar;Trusted_Connection=True;MultipleActiveResultSets=True;TrustServerCertificate=True;";
            }
            return defaultConn;
        }

        var sub = httpContext.User.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value 
            ?? httpContext.User.FindFirst(ClaimTypes.NameIdentifier)?.Value;

        if (string.IsNullOrEmpty(sub))
        {
            var defaultConn = _configuration.GetConnectionString("CuadreConnection");
            if (string.IsNullOrEmpty(defaultConn))
            {
                defaultConn = "Server=localhost;Database=SADEEstandar;Trusted_Connection=True;MultipleActiveResultSets=True;TrustServerCertificate=True;";
            }
            return defaultConn;
        }

        // Consultar CBSRepository para armar la cadena
        using var scope = _serviceProvider.CreateScope();
        var authDb = scope.ServiceProvider.GetRequiredService<AuthDbContext>();
        
        var userHasAccess = authDb.UsuarioEmpresas
            .AsEnumerable()
            .Any(ue => ue.IdEmpresa == idEmpresa && ue.IdSegUserGrp.Trim().Equals(sub.Trim(), StringComparison.OrdinalIgnoreCase));
            
        if (!userHasAccess)
        {
            throw new UnauthorizedAccessException("El usuario no tiene acceso a la empresa seleccionada.");
        }

        var empresa = authDb.Empresas.FirstOrDefault(e => e.IdEmpresa == idEmpresa && e.Activa && e.AccesoWeb);
        if (empresa == null)
        {
            throw new UnauthorizedAccessException("Empresa no válida, inactiva o sin acceso web.");
        }

        var servidor = empresa.Servidor?.Trim() ?? "";
        
        // Parche de Servidor Local: En base de datos de desarrollo a veces apunta a IPs de producción (ej. 10.0.0.6)
        if (servidor == "10.0.0.6" || servidor == "127.0.0.6" || servidor == "127.0.0.1" || servidor.ToLower() == "localhost") 
        {
            servidor = "localhost";
        }

        var baseDatos = empresa.BaseDatos?.Trim() ?? "";
        
        var builder = new SqlConnectionStringBuilder();
        builder.DataSource = servidor;
        builder.InitialCatalog = baseDatos;
        builder.TrustServerCertificate = true;
        builder.Encrypt = false;
        builder.MultipleActiveResultSets = true;
        
        // Read template connection to inherit SQL authentication credentials if configured
        var templateConn = _configuration.GetConnectionString("CuadreConnection");
        if (!string.IsNullOrEmpty(templateConn))
        {
            try
            {
                var templateBuilder = new SqlConnectionStringBuilder(templateConn);
                if (templateBuilder.IntegratedSecurity || string.IsNullOrEmpty(templateBuilder.UserID))
                {
                    builder.IntegratedSecurity = true;
                }
                else
                {
                    builder.UserID = templateBuilder.UserID;
                    builder.Password = templateBuilder.Password;
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[CORS / CONN ERROR] Fallback to IntegratedSecurity due to: {ex.Message}");
                builder.IntegratedSecurity = true;
            }
        }
        else
        {
            builder.IntegratedSecurity = true;
        }
        
        var connectionString = builder.ConnectionString;
        Console.WriteLine($"[DYNAMIC DB CONNECTION STRING RESOLVED] -> DataSource: '{servidor}', DB: '{baseDatos}' (SQL Auth: {!builder.IntegratedSecurity})");
        
        return connectionString;
    }
}
