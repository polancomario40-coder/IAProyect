using ControlPuertaAPI.Models;
using ControlPuertaAPI.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;
using System.IdentityModel.Tokens.Jwt;

namespace ControlPuertaAPI.Controllers;

/// <summary>
/// Auth endpoint compatible con el auth-center SSO.
/// Ruta: /api/usuario/validar-acceso
/// Recibe: Header X-Selected-Company (idEmpresa GUID), Header X-Client-Id
/// Retorna: { success, companiaNombre }
/// </summary>
[ApiController]
[Route("api/usuario")]
[Authorize]
public class UsuarioController : ControllerBase
{
    private readonly IConnectionFactory _cf;

    public UsuarioController(IConnectionFactory cf)
    {
        _cf = cf;
    }

    // ──────────────────────────────────────────────────────────────────────────
    // POST /api/usuario/validar-acceso
    // Llamado por auth-center después de que el usuario selecciona la empresa.
    // Valida que el usuario tenga acceso a sadegate y devuelve el nombre de empresa.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpPost("validar-acceso")]
    public async Task<IActionResult> ValidarAcceso()
    {
        try
        {
            // El JWT ya fue validado por el middleware [Authorize].
            // Solo necesitamos devolver el nombre de la empresa seleccionada.
            var idEmpresaStr = Request.Headers["X-Selected-Company"].ToString();

            // Obtener nombre de empresa desde la BD si existe, o devolver genérico
            string companiaNombre = "SADE";

            var sub = User.FindFirst(JwtRegisteredClaimNames.Sub)?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
            var roles = new List<string>();

            if (!string.IsNullOrWhiteSpace(idEmpresaStr) || !string.IsNullOrWhiteSpace(sub))
            {
                try
                {
                    await using var conn = _cf.CreateErpConnection();
                    await conn.OpenAsync();

                    // Intentar obtener nombre de empresa del catálogo de empresas
                    if (!string.IsNullOrWhiteSpace(idEmpresaStr))
                    {
                        await using var cmd = conn.CreateCommand();
                        cmd.CommandText = @"
                            SELECT TOP 1 Empresa 
                            FROM [SADE_Auth].[dbo].[Empresas] 
                            WHERE IdEmpresa = @id";
                        cmd.Parameters.AddWithValue("@id", idEmpresaStr);
                        var result = await cmd.ExecuteScalarAsync();
                        if (result != null && result != DBNull.Value)
                            companiaNombre = result.ToString()!;
                    }

                    // Intentar obtener roles del usuario en la BD del ERP
                    if (!string.IsNullOrWhiteSpace(sub))
                    {
                        await using var cmdRoles = conn.CreateCommand();
                        cmdRoles.CommandText = @"
                            SELECT idSegGrupo 
                            FROM SegUserinGrp 
                            WHERE idSegUser = @usuario";
                        cmdRoles.Parameters.AddWithValue("@usuario", sub.Trim());
                        using var reader = await cmdRoles.ExecuteReaderAsync();
                        while (await reader.ReadAsync())
                        {
                            roles.Add(reader.GetString(0).Trim());
                        }
                    }
                }
                catch
                {
                    // Ignorar errores de BD y continuar con roles vacíos y nombre por defecto
                }
            }

            return Ok(new { success = true, companiaNombre, roles });
        }
        catch (Exception ex)
        {
            return Ok(new { success = false, mensaje = $"Error al validar acceso: {ex.Message}" });
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // GET /api/usuario/me
    // Devuelve los datos y roles del usuario autenticado para que el frontend (SADEGate) sepa qué mostrar.
    // ──────────────────────────────────────────────────────────────────────────
    [HttpGet("me")]
    public async Task<IActionResult> GetMe()
    {
        try
        {
            var sub = User.FindFirst(JwtRegisteredClaimNames.Sub)?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
            var roles = new List<string>();

            if (!string.IsNullOrWhiteSpace(sub))
            {
                try
                {
                    await using var conn = _cf.CreateErpConnection();
                    await conn.OpenAsync();
                    await using var cmdRoles = conn.CreateCommand();
                    cmdRoles.CommandText = @"
                        SELECT idSegGrupo 
                        FROM SegUserinGrp 
                        WHERE idSegUser = @usuario";
                    cmdRoles.Parameters.AddWithValue("@usuario", sub.Trim());
                    using var reader = await cmdRoles.ExecuteReaderAsync();
                    while (await reader.ReadAsync())
                    {
                        roles.Add(reader.GetString(0).Trim());
                    }
                }
                catch
                {
                    // Ignorar errores de BD y continuar con roles vacíos
                }
            }

            return Ok(new { success = true, usuario = sub, roles });
        }
        catch (Exception ex)
        {
            return Ok(new { success = false, mensaje = $"Error al obtener usuario: {ex.Message}" });
        }
    }
}
