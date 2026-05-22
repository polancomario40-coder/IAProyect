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

            // Validate if user belongs to Administracion or Contabilidad
            var erpConnProvider = HttpContext.RequestServices.GetRequiredService<CuadreApi.Providers.IErpConnectionProvider>();
            var erpConnStr = erpConnProvider.GetConnectionString();
            using var erpConnection = new Microsoft.Data.SqlClient.SqlConnection(erpConnStr);
            await erpConnection.OpenAsync();

            using (var cmd = erpConnection.CreateCommand())
            {
                cmd.CommandText = "SELECT COUNT(1) FROM SegUserinGrp WHERE idSegUser = @user AND idSegGrupo IN ('Administracion', 'Contabilidad')";
                var pUser = cmd.CreateParameter();
                pUser.ParameterName = "@user";
                pUser.Value = subTrimmed;
                cmd.Parameters.Add(pUser);
                
                var count = Convert.ToInt32(await cmd.ExecuteScalarAsync());
                if (count == 0)
                {
                    return Ok(new { success = false, mensaje = "Su usuario no pertenece a los grupos autorizados (Administración o Contabilidad) para acceder al Cuadre de Caja." });
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

            // Para Cuadre de Caja en desarrollo local, permitimos acceso directamente
            return Ok(new { success = true, companiaNombre });
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
        var sub = User.FindFirst(JwtRegisteredClaimNames.Sub)?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        if (string.IsNullOrEmpty(sub))
        {
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
}
