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
    [Authorize]
    [ApiController]
    [Route("api/[controller]")]
    public class UsersController : ControllerBase
    {
        private readonly IDatabaseService _databaseService;
        private readonly ICryptoService _cryptoService;

        public UsersController(IDatabaseService databaseService, ICryptoService cryptoService)
        {
            _databaseService = databaseService;
            _cryptoService = cryptoService;
        }

        private string GetCompanyConnectionString()
        {
            return User.FindFirst("CompanyConnString")?.Value;
        }

        private Guid GetCompanyId()
        {
            var claim = User.FindFirst("CompanyId");
            return claim != null ? Guid.Parse(claim.Value) : Guid.Empty;
        }

        [HttpGet]
        public IActionResult GetGlobalUsers()
        {
            try
            {
                var list = new List<UserDto>();
                using (var conn = _databaseService.GetRepositoryConnection())
                {
                    conn.Open();
                    // We list all global users from CBSRepository
                    using (var cmd = new SqlCommand("cfgRSUsuario", conn))
                    {
                        cmd.CommandType = CommandType.StoredProcedure;
                        using (var reader = cmd.ExecuteReader())
                        {
                            while (reader.Read())
                            {
                                list.Add(new UserDto
                                {
                                    IdSegUserGrp = reader.GetString(reader.GetOrdinal("idSegUserGrp")),
                                    EsGrupo = reader.GetBoolean(reader.GetOrdinal("esGrupo")),
                                    ObjetoDefault = reader.IsDBNull(reader.GetOrdinal("ObjetoDefault")) ? "" : reader.GetString(reader.GetOrdinal("ObjetoDefault")),
                                    Activo = reader.IsDBNull(reader.GetOrdinal("Activo")) ? false : reader.GetBoolean(reader.GetOrdinal("Activo")),
                                    Nivel = reader.IsDBNull(reader.GetOrdinal("Nivel")) ? 3 : reader.GetInt32(reader.GetOrdinal("Nivel")),
                                    Email = reader.IsDBNull(reader.GetOrdinal("Email")) ? "" : reader.GetString(reader.GetOrdinal("Email")),
                                    Nombre = reader.IsDBNull(reader.GetOrdinal("Nombre")) ? "" : reader.GetString(reader.GetOrdinal("Nombre")),
                                    Telefono = reader.IsDBNull(reader.GetOrdinal("Telefono")) ? "" : reader.GetString(reader.GetOrdinal("Telefono")),
                                    CambiarClave = reader.IsDBNull(reader.GetOrdinal("CambiarClave")) ? false : reader.GetBoolean(reader.GetOrdinal("CambiarClave"))
                                });
                            }
                        }
                    }
                }
                return Ok(list);
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al obtener usuarios globales: {ex.Message}");
            }
        }

        [HttpPost]
        public IActionResult CreateUser([FromBody] UserDto user)
        {
            if (user == null || string.IsNullOrEmpty(user.IdSegUserGrp) || string.IsNullOrEmpty(user.Clave))
            {
                return BadRequest("Identificador de usuario y contraseña son necesarios.");
            }

            string connStr = GetCompanyConnectionString();
            Guid companyId = GetCompanyId();

            try
            {
                // Encrypt password using SADE's algorithm
                string cypherPwd = _cryptoService.EncryptString(user.Clave);
                Guid userGuid = Guid.NewGuid();

                using (var repoConn = _databaseService.GetRepositoryConnection())
                {
                    repoConn.Open();

                    // Check if exists in CBSRepository
                    using (var checkCmd = new SqlCommand("SELECT COUNT(*) FROM SegUserGrp WHERE idSegUserGrp = @id", repoConn))
                    {
                        checkCmd.Parameters.AddWithValue("@id", user.IdSegUserGrp);
                        if ((int)checkCmd.ExecuteScalar() > 0)
                        {
                            return BadRequest("El usuario ya existe en el repositorio global.");
                        }
                    }

                    // 1. Insert into CBSRepository..SegUserGrp
                    string repoInsert = @"
                        INSERT INTO SegUserGrp (idSegUserGrp, Clave, esGrupo, ObjetoDefault, Activo, Nivel, GuidUserGrp, Email, Nombre, Telefono, CambiarClave, Encriptada)
                        VALUES (@id, @Clave, 0, @ObjetoDefault, @Activo, @Nivel, @Guid, @Email, @Nombre, @Telefono, 1, 1)";

                    using (var cmd = new SqlCommand(repoInsert, repoConn))
                    {
                        cmd.Parameters.AddWithValue("@id", user.IdSegUserGrp);
                        cmd.Parameters.AddWithValue("@Clave", cypherPwd);
                        cmd.Parameters.AddWithValue("@ObjetoDefault", user.ObjetoDefault ?? "");
                        cmd.Parameters.AddWithValue("@Activo", user.Activo);
                        cmd.Parameters.AddWithValue("@Nivel", user.Nivel);
                        cmd.Parameters.AddWithValue("@Guid", userGuid);
                        cmd.Parameters.AddWithValue("@Email", user.Email ?? "");
                        cmd.Parameters.AddWithValue("@Nombre", user.Nombre ?? "");
                        cmd.Parameters.AddWithValue("@Telefono", user.Telefono ?? "");
                        cmd.ExecuteNonQuery();
                    }

                    // 2. Map user to the current company in CBSRepository
                    if (companyId != Guid.Empty)
                    {
                        string mapQuery = "INSERT INTO SegUserGrpEmpresa (idEmpresa, idSegUserGrp) VALUES (@idEmpresa, @idSegUserGrp)";
                        using (var cmd = new SqlCommand(mapQuery, repoConn))
                        {
                            cmd.Parameters.AddWithValue("@idEmpresa", companyId);
                            cmd.Parameters.AddWithValue("@idSegUserGrp", user.IdSegUserGrp);
                            cmd.ExecuteNonQuery();
                        }
                    }
                }

                // 3. Insert into the local company database SegUserGrp
                if (!string.IsNullOrEmpty(connStr))
                {
                    using (var localConn = _databaseService.GetCompanyConnection(connStr))
                    {
                        localConn.Open();
                        string localInsert = @"
                            INSERT INTO SegUserGrp (idSegUserGrp, Clave, esGrupo, ObjetoDefault, Activo, Nivel, rowguid)
                            VALUES (@id, @Clave, 0, @ObjetoDefault, @Activo, @Nivel, @Guid)";

                        using (var cmd = new SqlCommand(localInsert, localConn))
                        {
                            cmd.Parameters.AddWithValue("@id", user.IdSegUserGrp);
                            cmd.Parameters.AddWithValue("@Clave", cypherPwd);
                            cmd.Parameters.AddWithValue("@ObjetoDefault", user.ObjetoDefault ?? "");
                            cmd.Parameters.AddWithValue("@Activo", user.Activo);
                            cmd.Parameters.AddWithValue("@Nivel", user.Nivel);
                            cmd.Parameters.AddWithValue("@Guid", userGuid);
                            cmd.ExecuteNonQuery();
                        }
                    }
                }

                return Ok("Usuario creado exitosamente.");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al crear usuario: {ex.Message}");
            }
        }

        [HttpPut("{username}")]
        public IActionResult UpdateUser(string username, [FromBody] UserDto user)
        {
            if (user == null || string.IsNullOrEmpty(username))
            {
                return BadRequest("Datos de usuario inválidos.");
            }

            string connStr = GetCompanyConnectionString();

            try
            {
                using (var repoConn = _databaseService.GetRepositoryConnection())
                {
                    repoConn.Open();

                    // 1. Update in CBSRepository..SegUserGrp
                    string repoUpdate = @"
                        UPDATE SegUserGrp SET 
                            ObjetoDefault = @ObjetoDefault, Activo = @Activo, Nivel = @Nivel, 
                            Email = @Email, Nombre = @Nombre, Telefono = @Telefono";

                    if (!string.IsNullOrEmpty(user.Clave))
                    {
                        repoUpdate += ", Clave = @Clave, Encriptada = 1";
                    }

                    repoUpdate += " WHERE idSegUserGrp = @id";

                    using (var cmd = new SqlCommand(repoUpdate, repoConn))
                    {
                        cmd.Parameters.AddWithValue("@id", username);
                        cmd.Parameters.AddWithValue("@ObjetoDefault", user.ObjetoDefault ?? "");
                        cmd.Parameters.AddWithValue("@Activo", user.Activo);
                        cmd.Parameters.AddWithValue("@Nivel", user.Nivel);
                        cmd.Parameters.AddWithValue("@Email", user.Email ?? "");
                        cmd.Parameters.AddWithValue("@Nombre", user.Nombre ?? "");
                        cmd.Parameters.AddWithValue("@Telefono", user.Telefono ?? "");

                        if (!string.IsNullOrEmpty(user.Clave))
                        {
                            string cypherPwd = _cryptoService.EncryptString(user.Clave);
                            cmd.Parameters.AddWithValue("@Clave", cypherPwd);
                        }

                        cmd.ExecuteNonQuery();
                    }
                }

                // 2. Update in local company database SegUserGrp
                if (!string.IsNullOrEmpty(connStr))
                {
                    using (var localConn = _databaseService.GetCompanyConnection(connStr))
                    {
                        localConn.Open();
                        
                        // Check if user exists locally. If not, it means they are global, so we insert them locally first
                        string localUpsert = @"
                            IF EXISTS (SELECT 1 FROM SegUserGrp WHERE idSegUserGrp = @id)
                            BEGIN
                                UPDATE SegUserGrp SET 
                                    ObjetoDefault = @ObjetoDefault, Activo = @Activo, Nivel = @Nivel
                                    " + (!string.IsNullOrEmpty(user.Clave) ? ", Clave = @Clave" : "") + @"
                                WHERE idSegUserGrp = @id
                            END
                            ELSE
                            BEGIN
                                INSERT INTO SegUserGrp (idSegUserGrp, Clave, esGrupo, ObjetoDefault, Activo, Nivel, rowguid)
                                SELECT idSegUserGrp, Clave, esGrupo, ObjetoDefault, Activo, Nivel, GuidUserGrp
                                FROM cbsrepository..SegUserGrp
                                WHERE idSegUserGrp = @id
                            END";

                        using (var cmd = new SqlCommand(localUpsert, localConn))
                        {
                            cmd.Parameters.AddWithValue("@id", username);
                            cmd.Parameters.AddWithValue("@ObjetoDefault", user.ObjetoDefault ?? "");
                            cmd.Parameters.AddWithValue("@Activo", user.Activo);
                            cmd.Parameters.AddWithValue("@Nivel", user.Nivel);

                            if (!string.IsNullOrEmpty(user.Clave))
                            {
                                string cypherPwd = _cryptoService.EncryptString(user.Clave);
                                cmd.Parameters.AddWithValue("@Clave", cypherPwd);
                            }

                            cmd.ExecuteNonQuery();
                        }
                    }
                }

                return Ok("Usuario modificado exitosamente.");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al actualizar usuario: {ex.Message}");
            }
        }

        [HttpDelete("{username}")]
        public IActionResult DeleteUser(string username)
        {
            if (string.IsNullOrEmpty(username))
            {
                return BadRequest("Identificador de usuario es necesario.");
            }

            string connStr = GetCompanyConnectionString();

            try
            {
                using (var repoConn = _databaseService.GetRepositoryConnection())
                {
                    repoConn.Open();
                    // Deactivate user globally
                    using (var cmd = new SqlCommand("UPDATE SegUserGrp SET Activo = 0 WHERE idSegUserGrp = @id", repoConn))
                    {
                        cmd.Parameters.AddWithValue("@id", username);
                        cmd.ExecuteNonQuery();
                    }
                }

                if (!string.IsNullOrEmpty(connStr))
                {
                    using (var localConn = _databaseService.GetCompanyConnection(connStr))
                    {
                        localConn.Open();
                        using (var cmd = new SqlCommand("UPDATE SegUserGrp SET Activo = 0 WHERE idSegUserGrp = @id", localConn))
                        {
                            cmd.Parameters.AddWithValue("@id", username);
                            cmd.ExecuteNonQuery();
                        }
                    }
                }

                return Ok("Usuario desactivado exitosamente.");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al deactivar usuario: {ex.Message}");
            }
        }

        [HttpGet("{username}/companies")]
        public IActionResult GetUserCompanies(string username)
        {
            try
            {
                var companies = new List<Guid>();
                using (var conn = _databaseService.GetRepositoryConnection())
                {
                    conn.Open();
                    string query = "SELECT idEmpresa FROM SegUserGrpEmpresa WHERE idSegUserGrp = @idUser";
                    using (var cmd = new SqlCommand(query, conn))
                    {
                        cmd.Parameters.AddWithValue("@idUser", username);
                        using (var reader = cmd.ExecuteReader())
                        {
                            while (reader.Read())
                            {
                                companies.Add(reader.GetGuid(0));
                            }
                        }
                    }
                }
                return Ok(companies);
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al obtener asignación de empresas: {ex.Message}");
            }
        }

        [HttpPost("{username}/companies")]
        public IActionResult SaveUserCompanies(string username, [FromBody] List<Guid> companyIds)
        {
            if (string.IsNullOrEmpty(username) || companyIds == null)
            {
                return BadRequest("Parámetros inválidos.");
            }

            try
            {
                using (var conn = _databaseService.GetRepositoryConnection())
                {
                    conn.Open();
                    using (var transaction = conn.BeginTransaction())
                    {
                        try
                        {
                            // 1. Delete existing maps
                            string deleteQuery = "DELETE FROM SegUserGrpEmpresa WHERE idSegUserGrp = @idUser";
                            using (var cmd = new SqlCommand(deleteQuery, conn, transaction))
                            {
                                cmd.Parameters.AddWithValue("@idUser", username);
                                cmd.ExecuteNonQuery();
                            }

                            // 2. Insert new maps
                            foreach (var companyId in companyIds)
                            {
                                string insertQuery = "INSERT INTO SegUserGrpEmpresa (idEmpresa, idSegUserGrp) VALUES (@idCia, @idUser)";
                                using (var cmd = new SqlCommand(insertQuery, conn, transaction))
                                {
                                    cmd.Parameters.AddWithValue("@idCia", companyId);
                                    cmd.Parameters.AddWithValue("@idUser", username);
                                    cmd.ExecuteNonQuery();
                                }
                            }

                            transaction.Commit();
                        }
                        catch
                        {
                            transaction.Rollback();
                            throw;
                        }
                    }
                }
                return Ok("Mapeo de empresas de usuario actualizado exitosamente.");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al guardar asignación de empresas: {ex.Message}");
            }
        }
    }
}
