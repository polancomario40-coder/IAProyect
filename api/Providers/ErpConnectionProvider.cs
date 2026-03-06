using System.Security.Claims;
using CxpApi.Data;
using Microsoft.EntityFrameworkCore;

namespace CxpApi.Providers;

public interface IErpConnectionProvider
{
    string GetConnectionString();
}

public class ErpConnectionProvider : IErpConnectionProvider
{
    private readonly IHttpContextAccessor _httpContextAccessor;
    private readonly IServiceProvider _serviceProvider;

    public ErpConnectionProvider(IHttpContextAccessor httpContextAccessor, IServiceProvider serviceProvider)
    {
        _httpContextAccessor = httpContextAccessor;
        _serviceProvider = serviceProvider;
    }

    public string GetConnectionString()
    {
        var httpContext = _httpContextAccessor.HttpContext;
        if (httpContext?.User.Identity?.IsAuthenticated != true)
        {
            throw new UnauthorizedAccessException("El usuario no está autenticado.");
        }

        var sub = httpContext.User.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value 
            ?? httpContext.User.FindFirst(ClaimTypes.NameIdentifier)?.Value;

        if (string.IsNullOrEmpty(sub))
        {
            throw new UnauthorizedAccessException("Token no contiene identificación de usuario válida.");
        }

        var selectedCompanyHeader = httpContext.Request.Headers["X-Selected-Company"].FirstOrDefault();
        if (string.IsNullOrEmpty(selectedCompanyHeader) || !Guid.TryParse(selectedCompanyHeader, out Guid idEmpresa))
        {
            throw new UnauthorizedAccessException("Cabecera X-Selected-Company requerida y/o inválida.");
        }

        // Consultar CBSRepository para armar la cadena
        using var scope = _serviceProvider.CreateScope();
        var authDb = scope.ServiceProvider.GetRequiredService<AuthDbContext>();
        
        var userHasAccess = authDb.UsuarioEmpresas.Any(ue => ue.IdEmpresa == idEmpresa && ue.IdSegUserGrp == sub);
        if (!userHasAccess)
        {
            throw new UnauthorizedAccessException("El usuario no tiene acceso a la empresa seleccionada.");
        }

        var empresa = authDb.Empresas.FirstOrDefault(e => e.IdEmpresa == idEmpresa && e.Activa && e.AccesoWeb);
        if (empresa == null)
        {
            throw new UnauthorizedAccessException("Empresa no válida, inactiva o sin acceso web.");
        }

        // Construcción de la cadena de conexión basada en cfgempresa
        var connectionString = $"Server={empresa.Servidor};Database={empresa.BaseDatos};";
        
        if (empresa.Trusted)
        {
            connectionString += "Trusted_Connection=True;";
        }
        else
        {
            var userPwd = empresa.Encriptada ? DesencriptarPassword(empresa.UserPwd) : empresa.UserPwd;
            connectionString += $"User Id={empresa.UserId};Password={userPwd};";
        }
        
        connectionString += "TrustServerCertificate=True;";
        return connectionString;
    }

    private string DesencriptarPassword(string? pass)
    {
        // TODO: Implementar el mismo algoritmo de desencriptación de Delphi 7
        return pass ?? string.Empty;
    }
}
