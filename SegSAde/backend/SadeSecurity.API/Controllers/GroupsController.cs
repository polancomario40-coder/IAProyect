using System;
using System.Collections.Generic;
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
    public class GroupsController : ControllerBase
    {
        private readonly IDatabaseService _databaseService;

        public GroupsController(IDatabaseService databaseService)
        {
            _databaseService = databaseService;
        }

        private string GetCompanyConnectionString()
        {
            return User.FindFirst("CompanyConnString")?.Value;
        }

        [HttpGet]
        public IActionResult GetGroups()
        {
            string connStr = GetCompanyConnectionString();
            if (string.IsNullOrEmpty(connStr))
            {
                return BadRequest("No ha seleccionado ninguna empresa activa.");
            }

            try
            {
                var list = new List<GroupDto>();
                using (var conn = _databaseService.GetCompanyConnection(connStr))
                {
                    conn.Open();
                    string query = "SELECT idSegUserGrp, esGrupo, Activo, Nivel FROM SegUserGrp WHERE esGrupo = 1 ORDER BY idSegUserGrp";
                    using (var cmd = new SqlCommand(query, conn))
                    {
                        using (var reader = cmd.ExecuteReader())
                        {
                            while (reader.Read())
                            {
                                list.Add(new GroupDto
                                {
                                    IdSegUserGrp = reader.GetString(0),
                                    EsGrupo = reader.GetBoolean(1),
                                    Activo = reader.IsDBNull(2) ? false : reader.GetBoolean(2),
                                    Nivel = reader.IsDBNull(3) ? 3 : reader.GetInt32(3)
                                });
                            }
                        }
                    }
                }
                return Ok(list);
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al obtener grupos: {ex.Message}");
            }
        }

        [HttpPost]
        public IActionResult CreateGroup([FromBody] GroupDto group)
        {
            if (group == null || string.IsNullOrEmpty(group.IdSegUserGrp))
            {
                return BadRequest("Identificador de grupo es necesario.");
            }

            string connStr = GetCompanyConnectionString();

            try
            {
                Guid groupGuid = Guid.NewGuid();

                using (var repoConn = _databaseService.GetRepositoryConnection())
                {
                    repoConn.Open();
                    // Check if group already exists globally
                    using (var checkCmd = new SqlCommand("SELECT COUNT(*) FROM SegUserGrp WHERE idSegUserGrp = @id", repoConn))
                    {
                        checkCmd.Parameters.AddWithValue("@id", group.IdSegUserGrp);
                        if ((int)checkCmd.ExecuteScalar() > 0)
                        {
                            return BadRequest("El grupo ya existe en el repositorio global.");
                        }
                    }

                    // 1. Insert into CBSRepository..SegUserGrp
                    string repoInsert = @"
                        INSERT INTO SegUserGrp (idSegUserGrp, Clave, esGrupo, ObjetoDefault, Activo, Nivel, GuidUserGrp, Nombre, Encriptada)
                        VALUES (@id, '', 1, '', @Activo, @Nivel, @Guid, @Nombre, 0)";

                    using (var cmd = new SqlCommand(repoInsert, repoConn))
                    {
                        cmd.Parameters.AddWithValue("@id", group.IdSegUserGrp);
                        cmd.Parameters.AddWithValue("@Activo", group.Activo);
                        cmd.Parameters.AddWithValue("@Nivel", group.Nivel);
                        cmd.Parameters.AddWithValue("@Guid", groupGuid);
                        cmd.Parameters.AddWithValue("@Nombre", group.Nombre ?? group.IdSegUserGrp);
                        cmd.ExecuteNonQuery();
                    }
                }

                // 2. Insert into local company database
                if (!string.IsNullOrEmpty(connStr))
                {
                    using (var localConn = _databaseService.GetCompanyConnection(connStr))
                    {
                        localConn.Open();
                        string localInsert = @"
                            INSERT INTO SegUserGrp (idSegUserGrp, Clave, esGrupo, ObjetoDefault, Activo, Nivel, rowguid)
                            VALUES (@id, '', 1, '', @Activo, @Nivel, @Guid)";

                        using (var cmd = new SqlCommand(localInsert, localConn))
                        {
                            cmd.Parameters.AddWithValue("@id", group.IdSegUserGrp);
                            cmd.Parameters.AddWithValue("@Activo", group.Activo);
                            cmd.Parameters.AddWithValue("@Nivel", group.Nivel);
                            cmd.Parameters.AddWithValue("@Guid", groupGuid);
                            cmd.ExecuteNonQuery();
                        }
                    }
                }

                return Ok("Grupo creado exitosamente.");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al crear grupo: {ex.Message}");
            }
        }

        [HttpPut("{groupId}")]
        public IActionResult UpdateGroup(string groupId, [FromBody] GroupDto group)
        {
            if (group == null || string.IsNullOrEmpty(groupId))
            {
                return BadRequest("Datos de grupo inválidos.");
            }

            string connStr = GetCompanyConnectionString();

            try
            {
                using (var repoConn = _databaseService.GetRepositoryConnection())
                {
                    repoConn.Open();
                    // 1. Update globally
                    string repoUpdate = "UPDATE SegUserGrp SET Activo = @Activo, Nivel = @Nivel, Nombre = @Nombre WHERE idSegUserGrp = @id";
                    using (var cmd = new SqlCommand(repoUpdate, repoConn))
                    {
                        cmd.Parameters.AddWithValue("@id", groupId);
                        cmd.Parameters.AddWithValue("@Activo", group.Activo);
                        cmd.Parameters.AddWithValue("@Nivel", group.Nivel);
                        cmd.Parameters.AddWithValue("@Nombre", group.Nombre ?? groupId);
                        cmd.ExecuteNonQuery();
                    }
                }

                if (!string.IsNullOrEmpty(connStr))
                {
                    using (var localConn = _databaseService.GetCompanyConnection(connStr))
                    {
                        localConn.Open();
                        // 2. Update locally
                        string localUpdate = "UPDATE SegUserGrp SET Activo = @Activo, Nivel = @Nivel WHERE idSegUserGrp = @id";
                        using (var cmd = new SqlCommand(localUpdate, localConn))
                        {
                            cmd.Parameters.AddWithValue("@id", groupId);
                            cmd.Parameters.AddWithValue("@Activo", group.Activo);
                            cmd.Parameters.AddWithValue("@Nivel", group.Nivel);
                            cmd.ExecuteNonQuery();
                        }
                    }
                }

                return Ok("Grupo actualizado exitosamente.");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al actualizar grupo: {ex.Message}");
            }
        }

        [HttpDelete("{groupId}")]
        public IActionResult DeleteGroup(string groupId)
        {
            if (string.IsNullOrEmpty(groupId))
            {
                return BadRequest("Identificador de grupo es necesario.");
            }

            string connStr = GetCompanyConnectionString();

            try
            {
                using (var repoConn = _databaseService.GetRepositoryConnection())
                {
                    repoConn.Open();
                    using (var cmd = new SqlCommand("UPDATE SegUserGrp SET Activo = 0 WHERE idSegUserGrp = @id", repoConn))
                    {
                        cmd.Parameters.AddWithValue("@id", groupId);
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
                            cmd.Parameters.AddWithValue("@id", groupId);
                            cmd.ExecuteNonQuery();
                        }
                    }
                }

                return Ok("Grupo desactivado exitosamente.");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al eliminar grupo: {ex.Message}");
            }
        }

        [HttpGet("{groupId}/members")]
        public IActionResult GetGroupMembers(string groupId)
        {
            string connStr = GetCompanyConnectionString();
            if (string.IsNullOrEmpty(connStr))
            {
                return BadRequest("No ha seleccionado ninguna empresa activa.");
            }

            try
            {
                var members = new List<string>();
                using (var conn = _databaseService.GetCompanyConnection(connStr))
                {
                    conn.Open();
                    // Select * from SegUserinGrp where idSegGrupo = :idSegGrupo
                    string query = "SELECT idSegUser FROM SegUserinGrp WHERE idSegGrupo = @groupId";
                    using (var cmd = new SqlCommand(query, conn))
                    {
                        cmd.Parameters.AddWithValue("@groupId", groupId);
                        using (var reader = cmd.ExecuteReader())
                        {
                            while (reader.Read())
                            {
                                members.Add(reader.GetString(0));
                            }
                        }
                    }
                }
                return Ok(members);
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al obtener miembros del grupo: {ex.Message}");
            }
        }

        [HttpPost("{groupId}/members")]
        public IActionResult SaveGroupMembers(string groupId, [FromBody] List<string> usernames)
        {
            if (string.IsNullOrEmpty(groupId) || usernames == null)
            {
                return BadRequest("Parámetros inválidos.");
            }

            string connStr = GetCompanyConnectionString();
            if (string.IsNullOrEmpty(connStr))
            {
                return BadRequest("No ha seleccionado ninguna empresa activa.");
            }

            try
            {
                using (var conn = _databaseService.GetCompanyConnection(connStr))
                {
                    conn.Open();
                    using (var transaction = conn.BeginTransaction())
                    {
                        try
                        {
                            // 1. Delete existing maps for this group
                            string deleteQuery = "DELETE FROM SegUserinGrp WHERE idSegGrupo = @groupId";
                            using (var cmd = new SqlCommand(deleteQuery, conn, transaction))
                            {
                                cmd.Parameters.AddWithValue("@groupId", groupId);
                                cmd.ExecuteNonQuery();
                            }

                            // 2. Insert new maps
                            foreach (var username in usernames)
                            {
                                // Ensure user exists locally in the company database
                                string ensureLocalUserQuery = @"
                                    IF NOT EXISTS (SELECT 1 FROM SegUserGrp WHERE idSegUserGrp = @idUser)
                                    BEGIN
                                        INSERT INTO SegUserGrp (idSegUserGrp, Clave, esGrupo, ObjetoDefault, Activo, Nivel, rowguid)
                                        SELECT idSegUserGrp, Clave, esGrupo, ObjetoDefault, Activo, Nivel, GuidUserGrp
                                        FROM CBSRepository..SegUserGrp
                                        WHERE idSegUserGrp = @idUser
                                    END";
                                using (var cmd = new SqlCommand(ensureLocalUserQuery, conn, transaction))
                                {
                                    cmd.Parameters.AddWithValue("@idUser", username);
                                    cmd.ExecuteNonQuery();
                                }

                                string insertQuery = "INSERT INTO SegUserinGrp (idSegUser, idSegGrupo, rowguid) VALUES (@idUser, @groupId, NEWID())";
                                using (var cmd = new SqlCommand(insertQuery, conn, transaction))
                                {
                                    cmd.Parameters.AddWithValue("@idUser", username);
                                    cmd.Parameters.AddWithValue("@groupId", groupId);
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
                return Ok("Miembros del grupo actualizados exitosamente.");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al guardar miembros del grupo: {ex.Message}");
            }
        }
    }
}
