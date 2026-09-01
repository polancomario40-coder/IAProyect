using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using CuadreApi.Data;
using CuadreApi.Models;
using Microsoft.IdentityModel.Tokens;
using System;
using System.Collections.Generic;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Authorization;

namespace CuadreApi.Controllers;

public class LoginRequest
{
    public string Usuario { get; set; }
    public string Clave { get; set; }
}

[ApiController]
[Route("api/[controller]")]
public class LoginController : ControllerBase
{
    private readonly AuthDbContext _authDb;
    private readonly IConfiguration _configuration;

    public LoginController(AuthDbContext authDb, IConfiguration configuration)
    {
        _authDb = authDb;
        _configuration = configuration;
    }

    [HttpPost]
    public async Task<IActionResult> Login([FromBody] LoginRequest request)
    {
        try
        {
            Console.WriteLine($"[LOGIN ATTEMPT - SSO] User: '{request.Usuario}', Pass: '{request.Clave}'");
            var reqUser = request.Usuario?.Trim() ?? "";

            var usuario = await _authDb.Usuarios
                .FirstOrDefaultAsync(u => u.Username.Trim() == reqUser && u.Activo && !u.EsGrupo);

            Console.WriteLine($"[LOGIN QUERY RESULT] User Found: {usuario?.Username ?? "NULL"}");

            if (usuario == null)
                return Unauthorized("Credenciales incorrectas.");

            // Validar Password
            string dbPassword = usuario.Password?.Trim() ?? "";
            string inputPassword = request.Clave?.Trim() ?? "";

            Console.WriteLine($"[PWD MATCHING] DB: '{dbPassword}' (Len: {dbPassword.Length}), IN: '{inputPassword}' (Len: {inputPassword.Length}), Enc: {usuario.Encriptada}");

            bool isPasswordValid = false;
            if (usuario.Encriptada)
            {
                // Delphi Hash/Encriptación Placeholder
                isPasswordValid = dbPassword == EncriptarPassword(inputPassword);
            }
            else
            {
                isPasswordValid = dbPassword == inputPassword;
            }

            Console.WriteLine($"[PWD VALIDATED]: {isPasswordValid}");

            if (!isPasswordValid)
                return Unauthorized("Credenciales incorrectas.");

            // Generar JWT
            var tokenHandler = new JwtSecurityTokenHandler();
            var key = Encoding.ASCII.GetBytes(_configuration["Jwt:Key"] ?? string.Empty);
            
            var claims = new List<Claim>
            {
                new Claim(JwtRegisteredClaimNames.Sub, usuario.Username?.Trim() ?? ""),
                new Claim(JwtRegisteredClaimNames.Jti, usuario.GuidUserGrp.ToString()),
                new Claim(ClaimTypes.Role, usuario.Nivel.ToString()),
                new Claim(ClaimTypes.Name, usuario.Nombre?.Trim() ?? usuario.Username?.Trim() ?? "")
            };

            var tokenDescriptor = new SecurityTokenDescriptor
            {
                Subject = new ClaimsIdentity(claims),
                Expires = DateTime.UtcNow.AddHours(8),
                Issuer = _configuration["Jwt:Issuer"],
                Audience = _configuration["Jwt:Audience"],
                SigningCredentials = new SigningCredentials(new SymmetricSecurityKey(key), SecurityAlgorithms.HmacSha256Signature)
            };

            var token = tokenHandler.CreateToken(tokenDescriptor);

            return Ok(new
            {
                token = tokenHandler.WriteToken(token),
                cambiarClave = usuario.CambiarClave,
                usuario = new
                {
                    usuario.Username,
                    usuario.Nombre,
                    usuario.Nivel
                }
            });
        }
        catch (Exception ex)
        {
            var logPath = @"C:\inetpub\SADE\cuadre-api\api_debug.log";
            try { System.IO.File.AppendAllText(logPath, $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [LOGIN EXCEPTION] {ex.Message}\n{ex.StackTrace}\n"); } catch { }
            Console.WriteLine($"[LOGIN ERROR] {ex.Message}\n{ex.StackTrace}");
            return Ok(new { success = false, mensaje = "Error interno durante el login.", error = ex.Message });
        }
    }

    [HttpGet("test-token")]
    public IActionResult TestToken([FromQuery] string token)
    {
        var tokenHandler = new JwtSecurityTokenHandler();
        var key = Encoding.UTF8.GetBytes(_configuration["Jwt:Key"] ?? string.Empty);
        try
        {
            tokenHandler.ValidateToken(token, new TokenValidationParameters
            {
                ValidateIssuer = true,
                ValidateAudience = true,
                ValidateLifetime = true,
                ValidateIssuerSigningKey = true,
                ValidIssuer = _configuration["Jwt:Issuer"],
                ValidAudience = _configuration["Jwt:Audience"],
                IssuerSigningKey = new SymmetricSecurityKey(key)
            }, out SecurityToken validatedToken);
            return Ok(new { success = true, validatedToken = validatedToken.ToString() });
        }
        catch (Exception ex)
        {
            return Ok(new { success = false, error = ex.Message, stack = ex.StackTrace });
        }
    }

    private string EncriptarPassword(string pwd)
    {
        return pwd;
    }

    [Authorize]
    [HttpPost("~/api/usuario/validar-acceso")]
    public async Task<IActionResult> ValidarAcceso()
    {
        var sub = User.FindFirst(JwtRegisteredClaimNames.Sub)?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        if (string.IsNullOrEmpty(sub)) return Ok(new { success = false, mensaje = "Token inválido." });

        try
        {
            var subTrimmed = sub.Trim();

            var erpConnProvider = HttpContext.RequestServices.GetRequiredService<CuadreApi.Providers.IErpConnectionProvider>();
            var erpConnStr = erpConnProvider.GetConnectionString();
            using var erpConnection = new Microsoft.Data.SqlClient.SqlConnection(erpConnStr);
            await erpConnection.OpenAsync();

            // Read client id from header
            string clientId = Request.Headers.ContainsKey("X-Client-Id") ? Request.Headers["X-Client-Id"].ToString() : "";
            string requiredGroup = "cxpsade"; // default fallback for older apps
            string appName = "CXPAPP";
            
            if (clientId == "seg-sade")
            {
                requiredGroup = "System";
                appName = "Seguridad SADE";
            }
            else if (clientId == "cuadre-caja")
            {
                requiredGroup = "cxcsade";
                appName = "Cuadre de Caja";
            }

            using (var cmd = erpConnection.CreateCommand())
            {
                cmd.CommandText = "SELECT COUNT(1) FROM SegUserinGrp WHERE idSegUser = @user AND idSegGrupo = @grupo";
                var pUser = cmd.CreateParameter();
                pUser.ParameterName = "@user";
                pUser.Value = subTrimmed;
                cmd.Parameters.Add(pUser);

                var pGrupo = cmd.CreateParameter();
                pGrupo.ParameterName = "@grupo";
                pGrupo.Value = requiredGroup;
                cmd.Parameters.Add(pGrupo);
                
                var count = Convert.ToInt32(await cmd.ExecuteScalarAsync());
                if (count == 0)
                {
                    return Ok(new { success = false, mensaje = $"Su usuario no pertenece al grupo autorizado ({requiredGroup}) para acceder a {appName}." });
                }
            }

            string idEmpresaStr = Request.Headers["X-Selected-Company"].ToString();
            string companiaNombre = "";
            
            if (Guid.TryParse(idEmpresaStr, out Guid idEmpresa))
            {
                var emp = await _authDb.Empresas.FirstOrDefaultAsync(e => e.IdEmpresa == idEmpresa);
                if (emp != null)
                {
                    companiaNombre = emp.Empresa?.Trim() ?? "";
                }
            }

            int cobroStatus = 0;

            // Leer CXPVencida de la BD de la EMPRESA seleccionada (no del repositorio central)
            try { System.IO.File.AppendAllText(@"C:\inetpub\SADE\cuadre-api\publish\api_debug.log", $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [VENCIDAD START] idEmpresaStr='{idEmpresaStr}'\n"); } catch { }

            if (Guid.TryParse(idEmpresaStr, out Guid idEmpresaForConn))
            {
                try
                {
                    var empForConn = await _authDb.Empresas.FirstOrDefaultAsync(e => e.IdEmpresa == idEmpresaForConn);
                    if (empForConn != null)
                    {
                        var servidor = empForConn.Servidor?.Trim() ?? "localhost";
                        if (servidor == "10.0.0.6" || servidor == "127.0.0.1" || servidor.ToLower() == "localhost")
                            servidor = "localhost";
                        var baseDatos = empForConn.BaseDatos?.Trim() ?? "";

                        var empConnBuilder = new Microsoft.Data.SqlClient.SqlConnectionStringBuilder();
                        empConnBuilder.DataSource = servidor;
                        empConnBuilder.InitialCatalog = baseDatos;
                        empConnBuilder.TrustServerCertificate = true;
                        empConnBuilder.Encrypt = false;
                        empConnBuilder.MultipleActiveResultSets = true;

                        // Heredar credenciales del template
                        var templateConn = _configuration.GetConnectionString("CuadreConnection");
                        if (!string.IsNullOrEmpty(templateConn))
                        {
                            var tpl = new Microsoft.Data.SqlClient.SqlConnectionStringBuilder(templateConn);
                            if (tpl.IntegratedSecurity || string.IsNullOrEmpty(tpl.UserID))
                                empConnBuilder.IntegratedSecurity = true;
                            else { empConnBuilder.UserID = tpl.UserID; empConnBuilder.Password = tpl.Password; }
                        }
                        else empConnBuilder.IntegratedSecurity = true;

                        using var empConn = new Microsoft.Data.SqlClient.SqlConnection(empConnBuilder.ConnectionString);
                        await empConn.OpenAsync();
                        using var cmd2 = empConn.CreateCommand();
                        cmd2.CommandText = "SELECT TOP 1 Valor FROM defaults WHERE Clave = 'CXPVencida'";
                        var vencidadObj = await cmd2.ExecuteScalarAsync();
                        if (vencidadObj != null && vencidadObj != DBNull.Value)
                            cobroStatus = Convert.ToInt32(vencidadObj);

                        try { System.IO.File.AppendAllText(@"C:\inetpub\SADE\cuadre-api\publish\api_debug.log", $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [VENCIDAD] DB: '{baseDatos}' | CXPVencida = {cobroStatus}\n"); } catch { }
                    }
                }
                catch (Exception ex)
                {
                    try { System.IO.File.AppendAllText(@"C:\inetpub\SADE\cuadre-api\publish\api_debug.log", $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [VENCIDAD ERROR] {ex.Message}\n"); } catch { }
                }
            }

            if (cobroStatus == 3)
            {
                return Ok(new { success = true, companiaNombre, cobroStatus, cobroMensaje = "Su acceso al sistema ERP SADE ha sido suspendido por falta de pago. Para reactivar el servicio comuníquese con SADE." });
            }

            string cobroMensaje = cobroStatus == 1
                ? "Le solicitamos amablemente ponerse al día con los pagos pendientes a la mayor brevedad posible para evitar la suspensión del servicio."
                : cobroStatus == 2
                    ? "Aviso importante: El plazo para regularizar su cuenta está próximo a vencer. De no recibirse el pago pendiente en los próximos días, el acceso al sistema ERP SADE será bloqueado temporalmente. La reactivación del servicio tendrá un costo de US$200.00, además del pago de los valores pendientes."
                    : "";

            try { System.IO.File.AppendAllText(@"C:\inetpub\SADE\cuadre-api\api_debug.log", $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [VENCIDAD] Status read from DB: {cobroStatus} para empresa {companiaNombre}\n"); } catch { }

            // Para Cuadre de Caja en desarrollo local, permitimos acceso directamente
            return Ok(new { success = true, companiaNombre, cobroStatus, cobroMensaje });
        }
        catch (Exception ex)
        {
            return Ok(new { success = false, mensaje = $"Error al validar accesos: {ex.Message}" });
        }
    }

    [Authorize]
    [HttpGet("~/api/usuario/empresas")]
    public async Task<IActionResult> GetEmpresas()
    {
        try
        {
            var logPath = @"C:\inetpub\SADE\cuadre-api\api_debug.log";
            try { System.IO.File.AppendAllText(logPath, $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [INSIDE GetEmpresas] Started execution. Authenticated: {User.Identity?.IsAuthenticated}\n"); } catch { }

            var sub = User.FindFirst(JwtRegisteredClaimNames.Sub)?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
            
            try { System.IO.File.AppendAllText(logPath, $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [INSIDE GetEmpresas] Extracted sub: {sub ?? "NULL"}\n"); } catch { }

            if (string.IsNullOrEmpty(sub))
            {
                try { System.IO.File.AppendAllText(logPath, $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [INSIDE GetEmpresas] Returning Unauthorized due to empty sub.\n"); } catch { }
                return Unauthorized("No se pudo identificar al usuario en el token.");
            }

            var subTrimmed = sub.Trim();

            var empresas = await (from c in _authDb.Empresas
                                  join u in _authDb.UsuarioEmpresas on c.IdEmpresa equals u.IdEmpresa
                                  where u.IdSegUserGrp.Trim() == subTrimmed && c.Activa && c.AccesoWeb
                                  select new
                                  {
                                      c.IdEmpresa,
                                      c.Empresa,
                                      c.RNC
                                  }).ToListAsync();

            return Ok(empresas);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[GET EMPRESAS ERROR] {ex.Message}\n{ex.StackTrace}");
            return Ok(new { success = false, mensaje = "Error al obtener empresas.", error = ex.Message });
        }
    }
}
