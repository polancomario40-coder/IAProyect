using System;
using System.Linq;
using System.Security.Claims;
using System.Threading.Tasks;
using Dapper;
using Microsoft.AspNetCore.Http;
using Microsoft.Data.SqlClient;
using Microsoft.Extensions.Configuration;

namespace SADE_DashboardAPI.Providers
{
    public class ErpConnectionProvider : IErpConnectionProvider
    {
        private readonly IHttpContextAccessor _httpContextAccessor;
        private readonly IConfiguration _configuration;

        public ErpConnectionProvider(IHttpContextAccessor httpContextAccessor, IConfiguration configuration)
        {
            _httpContextAccessor = httpContextAccessor;
            _configuration = configuration;
        }

        public async Task<string> GetConnectionStringAsync()
        {
            var httpContext = _httpContextAccessor.HttpContext;
            var selectedCompanyHeader = httpContext?.Request.Headers["X-Selected-Company"].FirstOrDefault();

            // Safe fallback logic: si no hay token o header
            if (httpContext?.User.Identity?.IsAuthenticated != true ||
                string.IsNullOrEmpty(selectedCompanyHeader) || 
                !Guid.TryParse(selectedCompanyHeader, out Guid idEmpresa))
            {
                return GetDefaultConnection();
            }

            var sub = httpContext.User.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value 
                ?? httpContext.User.FindFirst(ClaimTypes.NameIdentifier)?.Value;

            if (string.IsNullOrEmpty(sub))
            {
                return GetDefaultConnection();
            }

            var authConnectionString = _configuration.GetConnectionString("AuthConnection");
            if (string.IsNullOrEmpty(authConnectionString))
            {
                throw new InvalidOperationException("AuthConnection is missing from appsettings.json");
            }

            using var authDb = new SqlConnection(authConnectionString);

            var query = @"
                SELECT e.IdEmpresa, e.Empresa, e.Servidor, e.BaseDatos, e.Activa, e.AccesoWeb 
                FROM cfgempresa e
                INNER JOIN segusergrpempresa ue ON e.IdEmpresa = ue.idEmpresa
                WHERE e.IdEmpresa = @idEmpresa 
                  AND ue.idSegUserGrp = @sub 
                  AND e.Activa = 1 
                  AND e.AccesoWeb = 1";

            var empresa = await authDb.QueryFirstOrDefaultAsync<dynamic>(query, new { idEmpresa, sub });

            if (empresa == null)
            {
                throw new UnauthorizedAccessException("Empresa no válida, inactiva, sin acceso web, o el usuario no tiene permisos.");
            }

            string servidor = empresa.Servidor?.Trim() ?? "";
            
            // Parche de Servidor Local
            if (servidor == "10.0.0.6" || servidor == "127.0.0.6" || servidor == "127.0.0.1" || servidor.ToLower() == "localhost") 
            {
                servidor = "localhost";
            }

            string baseDatos = empresa.BaseDatos?.Trim() ?? "";
            
            var builder = new SqlConnectionStringBuilder();
            builder.DataSource = servidor;
            builder.InitialCatalog = baseDatos;
            builder.TrustServerCertificate = true;
            builder.Encrypt = false;
            builder.MultipleActiveResultSets = true;
            
            var templateConn = _configuration.GetConnectionString("DashboardConnection") ?? _configuration.GetConnectionString("DefaultConnection");
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
                catch
                {
                    builder.IntegratedSecurity = true;
                }
            }
            else
            {
                builder.IntegratedSecurity = true;
            }
            
            return builder.ConnectionString;
        }

        private string GetDefaultConnection()
        {
            var defaultConn = _configuration.GetConnectionString("DashboardConnection") ?? _configuration.GetConnectionString("DefaultConnection");
            if (string.IsNullOrEmpty(defaultConn))
            {
                defaultConn = "Server=localhost;Database=SADEEstandar;Trusted_Connection=True;MultipleActiveResultSets=True;TrustServerCertificate=True;";
            }
            return defaultConn;
        }
    }
}
