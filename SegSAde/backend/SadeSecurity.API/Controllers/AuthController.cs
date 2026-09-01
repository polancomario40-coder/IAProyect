using System;
using System.Collections.Generic;
using System.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Authorization;
using Microsoft.Data.SqlClient;
using SadeSecurity.API.Models;
using SadeSecurity.API.Services;

namespace SadeSecurity.API.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class AuthController : ControllerBase
    {
        private readonly IDatabaseService _databaseService;
        private readonly ICryptoService _cryptoService;
        private readonly ITokenService _tokenService;

        public AuthController(IDatabaseService databaseService, ICryptoService cryptoService, ITokenService tokenService)
        {
            _databaseService = databaseService;
            _cryptoService = cryptoService;
            _tokenService = tokenService;
        }

        [HttpPost("login")]
        public IActionResult Login([FromBody] LoginRequest request)
        {
            if (request == null || string.IsNullOrEmpty(request.Username) || string.IsNullOrEmpty(request.Password))
            {
                return BadRequest("Usuario y contraseña son requeridos.");
            }

            try
            {
                using (var conn = _databaseService.GetRepositoryConnection())
                {
                    conn.Open();
                    using (var cmd = new SqlCommand("cfgBuscarUsuario", conn))
                    {
                        cmd.CommandType = CommandType.StoredProcedure;
                        cmd.Parameters.AddWithValue("@idSegUserGrp", request.Username);

                        using (var reader = cmd.ExecuteReader())
                        {
                            if (reader.Read())
                            {
                                bool esGrupo = reader.GetBoolean(reader.GetOrdinal("esGrupo"));
                                bool activo = reader.GetBoolean(reader.GetOrdinal("Activo"));
                                int nivel = reader.GetInt32(reader.GetOrdinal("Nivel"));
                                string dbClave = reader.GetString(reader.GetOrdinal("Clave"));
                                string nombre = reader.IsDBNull(reader.GetOrdinal("Nombre")) ? "" : reader.GetString(reader.GetOrdinal("Nombre"));
                                string email = reader.IsDBNull(reader.GetOrdinal("Email")) ? "" : reader.GetString(reader.GetOrdinal("Email"));

                                if (esGrupo)
                                {
                                    return Unauthorized("No se permite iniciar sesión con una cuenta de grupo.");
                                }

                                if (!activo)
                                {
                                    return Unauthorized("La cuenta de usuario está desactivada o bloqueada.");
                                }

                                // Encrypt the input password using SADE's algorithm to compare
                                string cypherPwd = _cryptoService.EncryptString(request.Password);

                                // Match either the encrypted password or the cleartext password (for fallback)
                                if (dbClave == cypherPwd || dbClave == request.Password)
                                {
                                    // Generate a temporary login token without company context
                                    var token = _tokenService.GenerateToken(request.Username, nombre, email, nivel, "", "", "");
                                    
                                    // Log login event in CBSRepository
                                    LogSecurityEvent(conn, Guid.Empty, request.Username, "EVENT_LOGIN_OK", "Login", request.Username, "Inicio de sesion exitoso en el portal web.");

                                    return Ok(new LoginResponse
                                    {
                                        Token = token,
                                        Username = request.Username,
                                        FullName = nombre,
                                        Email = email,
                                        Nivel = nivel
                                    });
                                }
                            }
                        }
                    }

                    // If login fails, increment failed attempts or log
                    LogSecurityEvent(conn, Guid.Empty, request.Username, "EVENT_LOGIN_FAIL", "Login", request.Username, "Intento fallido de inicio de sesion.");
                }

                return Unauthorized("Usuario o contraseña incorrectos.");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error interno del servidor: {ex.Message}");
            }
        }

        [Authorize]
        [HttpGet("companies")]
        public IActionResult GetCompanies()
        {
            string username = User.Identity?.Name;
            if (string.IsNullOrEmpty(username))
            {
                return Unauthorized();
            }

            try
            {
                var companies = new List<CompanyDto>();
                using (var conn = _databaseService.GetRepositoryConnection())
                {
                    conn.Open();
                    using (var cmd = new SqlCommand("cfgRSEmpresasXUsr", conn))
                    {
                        cmd.CommandType = CommandType.StoredProcedure;
                        cmd.Parameters.AddWithValue("@idSegUserGrp", username);

                        using (var reader = cmd.ExecuteReader())
                        {
                            while (reader.Read())
                            {
                                companies.Add(new CompanyDto
                                {
                                    IdEmpresa = reader.GetGuid(reader.GetOrdinal("idEmpresa")),
                                    Empresa = reader.GetString(reader.GetOrdinal("Empresa")),
                                    RNC = reader.IsDBNull(reader.GetOrdinal("RNC")) ? "" : reader.GetString(reader.GetOrdinal("RNC")),
                                    Servidor = reader.IsDBNull(reader.GetOrdinal("Servidor")) ? "" : reader.GetString(reader.GetOrdinal("Servidor")),
                                    BaseDatos = reader.IsDBNull(reader.GetOrdinal("BaseDatos")) ? "" : reader.GetString(reader.GetOrdinal("BaseDatos")),
                                    Trusted = reader.IsDBNull(reader.GetOrdinal("Trusted")) ? false : reader.GetBoolean(reader.GetOrdinal("Trusted")),
                                    UserId = reader.IsDBNull(reader.GetOrdinal("UserId")) ? "" : reader.GetString(reader.GetOrdinal("UserId")),
                                    Activa = reader.IsDBNull(reader.GetOrdinal("Activa")) ? false : reader.GetBoolean(reader.GetOrdinal("Activa"))
                                });
                            }
                        }
                    }
                }
                return Ok(companies);
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al obtener empresas: {ex.Message}");
            }
        }

        [Authorize]
        [HttpPost("select-company")]
        public IActionResult SelectCompany([FromBody] SelectCompanyRequest request)
        {
            string username = User.Identity?.Name;
            if (string.IsNullOrEmpty(username) || request == null || string.IsNullOrEmpty(request.CompanyId))
            {
                return BadRequest("Selección de empresa inválida.");
            }

            try
            {
                Guid companyGuid = Guid.Parse(request.CompanyId);
                string companyConnStr = _databaseService.GetCompanyConnectionString(companyGuid);

                string companyName = "";
                string userEmail = "";
                string userFullName = "";
                int userNivel = 3;

                using (var conn = _databaseService.GetRepositoryConnection())
                {
                    conn.Open();
                    
                    // Fetch company name
                    using (var cmd = new SqlCommand("SELECT Empresa FROM cfgEmpresa WHERE idEmpresa = @idEmpresa", conn))
                    {
                        cmd.Parameters.AddWithValue("@idEmpresa", companyGuid);
                        companyName = cmd.ExecuteScalar()?.ToString() ?? "";
                    }

                    // Fetch user details
                    using (var cmd = new SqlCommand("cfgBuscarUsuario", conn))
                    {
                        cmd.CommandType = CommandType.StoredProcedure;
                        cmd.Parameters.AddWithValue("@idSegUserGrp", username);
                        using (var reader = cmd.ExecuteReader())
                        {
                            if (reader.Read())
                            {
                                userFullName = reader.IsDBNull(reader.GetOrdinal("Nombre")) ? "" : reader.GetString(reader.GetOrdinal("Nombre"));
                                userEmail = reader.IsDBNull(reader.GetOrdinal("Email")) ? "" : reader.GetString(reader.GetOrdinal("Email"));
                                userNivel = reader.GetInt32(reader.GetOrdinal("Nivel"));
                            }
                        }
                    }

                    LogSecurityEvent(conn, companyGuid, username, "EVENT_LOGIN_OK", "SelectCompany", companyName, $"Acceso concedido a la empresa {companyName}.");
                }

                // Generate new token containing the dynamic database connection parameters for that company
                var token = _tokenService.GenerateToken(username, userFullName, userEmail, userNivel, request.CompanyId, companyName, companyConnStr);

                return Ok(new
                {
                    Token = token,
                    Username = username,
                    FullName = userFullName,
                    Email = userEmail,
                    CompanyId = request.CompanyId,
                    CompanyName = companyName
                });
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al seleccionar empresa: {ex.Message}");
            }
        }

        [Authorize]
        [HttpPost("change-password")]
        public IActionResult ChangePassword([FromBody] ChangePasswordRequest request)
        {
            string username = User.Identity?.Name;
            if (string.IsNullOrEmpty(username) || request == null || string.IsNullOrEmpty(request.NewPassword))
            {
                return BadRequest("Datos de cambio de contraseña inválidos.");
            }

            try
            {
                using (var conn = _databaseService.GetRepositoryConnection())
                {
                    conn.Open();

                    // Check if current password is correct (if old password provided)
                    if (!string.IsNullOrEmpty(request.OldPassword))
                    {
                        using (var cmd = new SqlCommand("cfgBuscarUsuario", conn))
                        {
                            cmd.CommandType = CommandType.StoredProcedure;
                            cmd.Parameters.AddWithValue("@idSegUserGrp", username);
                            string dbClave = cmd.ExecuteScalar()?.ToString() ?? "";
                            string oldCypher = _cryptoService.EncryptString(request.OldPassword);

                            if (dbClave != oldCypher && dbClave != request.OldPassword)
                            {
                                return BadRequest("La contraseña actual es incorrecta.");
                            }
                        }
                    }

                    // Encrypt the new password
                    string newCypher = _cryptoService.EncryptString(request.NewPassword);

                    using (var cmd = new SqlCommand("UPDATE SegUserGrp SET Clave = @Clave, CambiarClave = 0 WHERE idSegUserGrp = @idSegUserGrp", conn))
                    {
                        cmd.Parameters.AddWithValue("@Clave", newCypher);
                        cmd.Parameters.AddWithValue("@idSegUserGrp", username);
                        cmd.ExecuteNonQuery();
                    }

                    LogSecurityEvent(conn, Guid.Empty, username, "EVENT_PASSWORD_CHANGED", "PasswordChange", username, "Cambio de contraseña exitoso.");
                }

                return Ok("Contraseña modificada exitosamente.");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al cambiar contraseña: {ex.Message}");
            }
        }

        private void LogSecurityEvent(SqlConnection conn, Guid companyId, string username, string eventName, string objName, string reference, string description)
        {
            try
            {
                using (var cmd = new SqlCommand("segInsertLog", conn))
                {
                    cmd.CommandType = CommandType.StoredProcedure;
                    cmd.Parameters.AddWithValue("@idEmpresa", companyId == Guid.Empty ? (object)DBNull.Value : companyId);
                    cmd.Parameters.AddWithValue("@Usuario", username ?? "guest");
                    cmd.Parameters.AddWithValue("@Evento", eventName);
                    cmd.Parameters.AddWithValue("@Objeto", objName);
                    cmd.Parameters.AddWithValue("@Referencia", reference ?? "");
                    cmd.Parameters.AddWithValue("@Descripcion", description ?? "");
                    cmd.Parameters.AddWithValue("@DatosAdd", "IP: " + HttpContext.Connection.RemoteIpAddress);
                    cmd.ExecuteNonQuery();
                }
            }
            catch
            {
                // Suppress audit logging failure to prevent blocking primary authentication flows
            }
        }
    }
}
