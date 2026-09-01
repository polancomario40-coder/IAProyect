using AuthGeneral.Data;
using AuthGeneral.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;

namespace AuthGeneral.Controllers;

[ApiController]
[Route("api")]
public class AuthController : ControllerBase
{
    private readonly AuthDbContext _authDb;
    private readonly IConfiguration _configuration;

    public AuthController(AuthDbContext authDb, IConfiguration configuration)
    {
        _authDb = authDb;
        _configuration = configuration;
    }

    [HttpPost("login")]
    public async Task<IActionResult> Login([FromBody] LoginRequest request)
    {
        string logPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "auth_debug.log");
        void Log(string msg) { try { System.IO.File.AppendAllText(logPath, msg); } catch {} }
        
        try
        {
            Log($"\n[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [LOGIN ATTEMPT] User: '{request.Usuario}'\n");

            if (string.IsNullOrWhiteSpace(request.Usuario) || string.IsNullOrWhiteSpace(request.Clave))
            {
                Log($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [LOGIN FAILED] Empty credentials.\n");
                return Ok(new { success = false, mensaje = "Usuario y contraseña son requeridos." });
            }

            var subTrimmed = request.Usuario.Trim();
            var inputPassword = request.Clave.Trim();
            
            var user = await _authDb.Usuarios.FirstOrDefaultAsync(u => u.Username.Trim() == subTrimmed && u.EsGrupo == false && u.Activo == true);

            if (user == null)
            {
                return Ok(new { success = false, mensaje = "Usuario o contraseña incorrectos." });
            }

            string dbPassword = user.Password?.Trim() ?? "";
            
            bool isPasswordValid = false;
            if (user.Encriptada)
            {
                isPasswordValid = dbPassword == EncriptarPassword(inputPassword);
            }
            else
            {
                isPasswordValid = dbPassword == inputPassword;
            }

            if (!isPasswordValid)
            {
                return Ok(new { success = false, mensaje = "Usuario o contraseña incorrectos." });
            }

            if (!user.Activo)
            {
                return Ok(new { success = false, mensaje = "El usuario está inactivo." });
            }

            var jwtKey = _configuration["Jwt:Key"];
            if (string.IsNullOrEmpty(jwtKey))
            {
                return StatusCode(500, new { success = false, mensaje = "Falta configuración JWT." });
            }

            var claims = new[]
            {
                new Claim(JwtRegisteredClaimNames.Sub, subTrimmed),
                new Claim(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString())
            };

            var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtKey));
            var creds = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);

            var token = new JwtSecurityToken(
                issuer: _configuration["Jwt:Issuer"],
                audience: _configuration["Jwt:Audience"],
                claims: claims,
                expires: DateTime.UtcNow.AddHours(8),
                signingCredentials: creds
            );

            var tokenString = new JwtSecurityTokenHandler().WriteToken(token);

            return Ok(new { success = true, token = tokenString, usuario = subTrimmed });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { success = false, mensaje = "Error interno del servidor.", error = ex.Message });
        }
    }

    [Authorize]
    [HttpGet("usuario/empresas")]
    public async Task<IActionResult> GetEmpresas()
    {
        try
        {
            var sub = User.FindFirst(JwtRegisteredClaimNames.Sub)?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;

            if (string.IsNullOrEmpty(sub))
            {
                return Unauthorized("No se pudo identificar al usuario en el token.");
            }

            var subTrimmed = sub.Trim();

            var empresas = await (from c in _authDb.Empresas
                                  join u in _authDb.UsuarioEmpresas on c.IdEmpresa equals u.IdEmpresa
                                  where u.IdSegUserGrp.Trim() == subTrimmed && c.Activa
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
            return Ok(new { success = false, mensaje = "Error al obtener empresas.", error = ex.Message });
        }
    }

    [Authorize]
    [HttpPost("usuario/validar-acceso")]
    public async Task<IActionResult> ValidarAcceso()
    {
        try
        {
            var sub = User.FindFirst(JwtRegisteredClaimNames.Sub)?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
            if (string.IsNullOrEmpty(sub)) return Unauthorized("No autorizado.");

            var subTrimmed = sub.Trim();
            string idEmpresaStr = Request.Headers["X-Selected-Company"].ToString();
            string clientId = Request.Headers["X-Client-Id"].ToString();

            string companiaNombre = "";
            if (Guid.TryParse(idEmpresaStr, out Guid idEmpresa))
            {
                var emp = await _authDb.Empresas.FirstOrDefaultAsync(e => e.IdEmpresa == idEmpresa);
                if (emp != null)
                {
                    companiaNombre = emp.Empresa?.Trim() ?? "";
                }
            }

            // Aquí se puede añadir validación genérica por client_id en la base de datos de la empresa si es necesario.
            // Por defecto, si el JWT es válido y seleccionó empresa, damos acceso.
            return Ok(new { success = true, companiaNombre });
        }
        catch (Exception ex)
        {
            return Ok(new { success = false, mensaje = $"Error al validar accesos: {ex.Message}" });
        }
    }
    private string EncriptarPassword(string pass)
    {
        if (string.IsNullOrEmpty(pass)) return string.Empty;
        ushort c1 = 52845;
        ushort c2 = 22719;
        ushort key = 2000;
        
        byte[] result = new byte[pass.Length];
        for (int i = 0; i < pass.Length; i++)
        {
            byte b = (byte)(pass[i] ^ (key >> 8));
            result[i] = b;
            key = (ushort)(((b + key) * c1 + c2) % 65536);
        }
        
        return BitConverter.ToString(result).Replace("-", "");
    }
}

public class LoginRequest
{
    public string Usuario { get; set; } = string.Empty;
    public string Clave { get; set; } = string.Empty;
}
