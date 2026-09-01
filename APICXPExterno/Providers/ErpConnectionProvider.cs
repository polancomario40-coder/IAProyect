using System.Security.Claims;
using CxpApi.Data;
using Microsoft.EntityFrameworkCore;

namespace CxpApi.Providers;

public interface IErpConnectionProvider
{
    string GetConnectionString();
    string GetConnectionString(Guid idEmpresa);
    string GetConnectionString(CxpApi.Models.CfgEmpresa empresa);
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
        
        var userHasAccess = authDb.UsuarioEmpresas
            .AsEnumerable()
            .Any(ue => ue.IdEmpresa == idEmpresa && ue.IdSegUserGrp.Trim() == sub.Trim());
        if (!userHasAccess)
        {
            throw new UnauthorizedAccessException("El usuario no tiene acceso a la empresa seleccionada.");
        }

        var empresa = authDb.Empresas.FirstOrDefault(e => e.IdEmpresa == idEmpresa && e.Activa && e.AccesoWeb);
        if (empresa == null)
        {
            throw new UnauthorizedAccessException("Empresa no válida, inactiva o sin acceso web.");
        }

        return GetConnectionString(empresa);
    }

    public string GetConnectionString(Guid idEmpresa)
    {
        using var scope = _serviceProvider.CreateScope();
        var authDb = scope.ServiceProvider.GetRequiredService<AuthDbContext>();
        var empresa = authDb.Empresas.FirstOrDefault(e => e.IdEmpresa == idEmpresa && e.Activa && e.AccesoWeb);
        if (empresa == null)
        {
            throw new UnauthorizedAccessException("Empresa no válida, inactiva o sin acceso web.");
        }
        return GetConnectionString(empresa);
    }

    public string GetConnectionString(CxpApi.Models.CfgEmpresa empresa)
    {
        var servidor = empresa.Servidor?.Trim() ?? "";
        
        // Parche de Servidor Local: SADEcon a veces guarda "127.0.0.6" en BD, fallando la resolución de ADO.NET
        if (servidor == "10.0.0.6" || servidor == "127.0.0.6" || servidor == "127.0.0.1" || servidor.ToLower() == "localhost") 
        {
            servidor = "localhost";
        }

        var baseDatos = empresa.BaseDatos?.Trim() ?? "";
        
        var builder = new Microsoft.Data.SqlClient.SqlConnectionStringBuilder();
        builder.DataSource = servidor;
        builder.InitialCatalog = baseDatos;
        builder.TrustServerCertificate = true;
        builder.Encrypt = false;
        
        if (empresa.Trusted == true)
        {
            builder.IntegratedSecurity = true;
        }
        else
        {
            var userId = empresa.Encriptada ? DesencriptarPassword(empresa.UserId?.Trim()) : empresa.UserId?.Trim();
            var userPwd = empresa.Encriptada ? DesencriptarPassword(empresa.UserPwd?.Trim()) : empresa.UserPwd?.Trim();
            builder.UserID = userId ?? "";
            builder.Password = userPwd ?? "";
        }
        
        var connectionString = builder.ConnectionString;
        Console.WriteLine($"[DB CONNECTION STRING BUILDER] -> {connectionString}");
        return connectionString;
    }

    private string DesencriptarPassword(string? pass)
    {
        // Limpiar espacios y caracteres nulos de Delphi (muy comun en CHAR(N))
        pass = pass?.Replace("\0", "").Trim();
        if (string.IsNullOrWhiteSpace(pass)) return string.Empty;
        
        // Validar longitud par antes de procesar para evitar ArgumentOutOfRangeException
        if (pass.Length % 2 != 0) return pass;

        try
        {
            ushort c1 = 52845;
            ushort c2 = 22719;
            ushort key = 2000;

            byte[] decodedBytes = new byte[pass.Length / 2];
            for (int i = 0; i < pass.Length; i += 2)
            {
                decodedBytes[i / 2] = Convert.ToByte(pass.Substring(i, 2), 16);
            }

            char[] resultStr = new char[decodedBytes.Length];
            for (int i = 0; i < decodedBytes.Length; i++)
            {
                resultStr[i] = (char)(decodedBytes[i] ^ (key >> 8));
                key = (ushort)(((decodedBytes[i] + key) * c1 + c2) % 65536);
            }

            return new string(resultStr);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[ERROR Desencriptando Password]: {ex.Message}");
            return pass ?? string.Empty;
        }
    }
}
