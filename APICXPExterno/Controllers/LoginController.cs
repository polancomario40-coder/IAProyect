using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using CxpApi.Data;
using Microsoft.IdentityModel.Tokens;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Microsoft.AspNetCore.Authorization;

namespace CxpApi.Controllers;

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
        Console.WriteLine($"[LOGIN ATTEMPT] User: '{request.Usuario}', Pass: '{request.Clave}'");
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
            // TODO: Ajustar a la función Hash/Encriptación de Delphi
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

    [HttpPost("debug")]
    public async Task<IActionResult> LoginDebug([FromBody] LoginRequest request)
    {
        var reqUser = request.Usuario?.Trim() ?? "";
        var usuario = await _authDb.Usuarios.FirstOrDefaultAsync(u => u.Username.Trim() == reqUser && u.Activo && !u.EsGrupo);
        if (usuario == null) return Ok(new { error = "user not found" });
        
        string dbPassword = usuario.Password?.Trim() ?? "";
        string inputPassword = request.Clave?.Trim() ?? "";
        bool isPasswordValid = false;
        
        if (usuario.Encriptada) isPasswordValid = dbPassword == EncriptarPassword(inputPassword);
        else isPasswordValid = dbPassword == inputPassword;

        return Ok(new { 
            dbPass = dbPassword, dbLen = dbPassword.Length,
            inPass = inputPassword, inLen = inputPassword.Length,
            enc = usuario.Encriptada,
            valid = isPasswordValid
        });
    }

    private string EncriptarPassword(string pwd)
    {
        // Placeholder
        return pwd;
    }

    [Authorize]
    [HttpPost("~/api/usuario/validar-acceso")]
    public async Task<IActionResult> ValidarAcceso([FromServices] AppDbContext erpDb)
    {
        var sub = User.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        if (string.IsNullOrEmpty(sub)) return Ok(new { success = false, mensaje = "Token inválido." });

        try
        {
            await erpDb.Database.OpenConnectionAsync();
            var connection = erpDb.Database.GetDbConnection();
            var command = connection.CreateCommand();
            
            command.CommandText = "SELECT idSegGrupo FROM SegUserinGrp WHERE idSegUser = @usuario";
            var pUser = command.CreateParameter();
            pUser.ParameterName = "@usuario";
            pUser.Value = sub.Trim();
            command.Parameters.Add(pUser);

            bool hasAccess = false;
            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                {
                    if (reader["idSegGrupo"]?.ToString()?.Trim().ToUpper() == "CXPAPP")
                    {
                        hasAccess = true;
                        break;
                    }
                }
            }

            string companiaNombre = "";
            if (hasAccess)
            {
                string idEmpresaStr = Request.Headers["X-Selected-Company"].ToString();
                if (Guid.TryParse(idEmpresaStr, out Guid idEmpresa))
                {
                    var emp = await _authDb.Empresas.FirstOrDefaultAsync(e => e.IdEmpresa == idEmpresa);
                    if (emp != null)
                    {
                        companiaNombre = emp.Empresa?.Trim() ?? "";
                    }
                }
                return Ok(new { success = true, companiaNombre });
            }
            
            return Ok(new { success = false, mensaje = "No tiene permisos requeridos (CXPAPP) para esta compañía." });
        }
        catch (Exception ex)
        {
            return Ok(new { success = false, mensaje = $"Error al validar accesos en ERP: {ex.Message}" });
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
