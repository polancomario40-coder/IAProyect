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
    public class PermissionsController : ControllerBase
    {
        private readonly IDatabaseService _databaseService;

        public PermissionsController(IDatabaseService databaseService)
        {
            _databaseService = databaseService;
        }

        private string GetCompanyConnectionString()
        {
            var claim = User.FindFirst("CompanyConnString");
            return claim?.Value;
        }

        [HttpGet("objects")]
        public IActionResult GetObjects()
        {
            string connStr = GetCompanyConnectionString();
            if (string.IsNullOrEmpty(connStr))
            {
                return BadRequest("No ha seleccionado ninguna empresa activa.");
            }

            try
            {
                var list = new List<ObjectDto>();
                using (var conn = _databaseService.GetCompanyConnection(connStr))
                {
                    conn.Open();
                    string query = "SELECT idSegObjeto, SegObjeto, TipoObjeto, Categoria FROM SegObjeto ORDER BY Categoria, idSegObjeto";
                    using (var cmd = new SqlCommand(query, conn))
                    {
                        using (var reader = cmd.ExecuteReader())
                        {
                            while (reader.Read())
                            {
                                list.Add(new ObjectDto
                                {
                                    IdSegObjeto = reader.GetString(0),
                                    SegObjeto = reader.IsDBNull(1) ? "" : reader.GetString(1),
                                    TipoObjeto = reader.IsDBNull(2) ? "" : reader.GetString(2),
                                    Categoria = reader.IsDBNull(3) ? "" : reader.GetString(3)
                                });
                            }
                        }
                    }
                }
                return Ok(list);
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al obtener objetos: {ex.Message}");
            }
        }

        [HttpGet("matrix")]
        public IActionResult GetMatrix([FromQuery] string userOrGroupId)
        {
            if (string.IsNullOrEmpty(userOrGroupId))
            {
                return BadRequest("idSegUserGrp es requerido.");
            }

            string connStr = GetCompanyConnectionString();
            if (string.IsNullOrEmpty(connStr))
            {
                return BadRequest("No ha seleccionado ninguna empresa activa.");
            }

            try
            {
                var list = new List<PermissionDto>();
                using (var conn = _databaseService.GetCompanyConnection(connStr))
                {
                    conn.Open();
                    
                    // We join SegObjeto with SegPermiso for the specified user or group.
                    // If no permission record exists yet, we return defaults (0).
                    string query = @"
                        SELECT 
                            o.idSegObjeto, 
                            o.SegObjeto, 
                            o.Categoria,
                            ISNULL(p.Agregar, 0) as Agregar,
                            ISNULL(p.Editar, 0) as Editar,
                            ISNULL(p.Borrar, 0) as Borrar,
                            ISNULL(p.Imprimir, 0) as Imprimir,
                            ISNULL(p.Abrir, 0) as Abrir,
                            ISNULL(p.Anular, 0) as Anular,
                            ISNULL(p.Aprobar, 0) as Aprobar
                        FROM SegObjeto o
                        LEFT JOIN SegPermiso p ON o.idSegObjeto = p.idSegObjeto AND p.idSegUserGrp = @UserOrGroup
                        ORDER BY o.Categoria, o.idSegObjeto";

                    using (var cmd = new SqlCommand(query, conn))
                    {
                        cmd.Parameters.AddWithValue("@UserOrGroup", userOrGroupId);
                        using (var reader = cmd.ExecuteReader())
                        {
                            while (reader.Read())
                            {
                                list.Add(new PermissionDto
                                {
                                    IdSegObjeto = reader.GetString(0),
                                    IdSegUserGrp = userOrGroupId,
                                    SegObjeto = reader.IsDBNull(1) ? "" : reader.GetString(1),
                                    Categoria = reader.IsDBNull(2) ? "" : reader.GetString(2),
                                    Agregar = reader.GetByte(3),
                                    Editar = reader.GetByte(4),
                                    Borrar = reader.GetByte(5),
                                    Imprimir = reader.GetByte(6),
                                    Abrir = reader.GetByte(7),
                                    Anular = reader.GetByte(8),
                                    Aprobar = reader.GetByte(9)
                                });
                            }
                        }
                    }
                }
                return Ok(list);
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al obtener matriz de permisos: {ex.Message}");
            }
        }

        [HttpPost("matrix")]
        public IActionResult SaveMatrix([FromBody] List<PermissionDto> permissions)
        {
            if (permissions == null || permissions.Count == 0)
            {
                return BadRequest("No se recibieron datos de permisos.");
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
                            foreach (var p in permissions)
                            {
                                // Ensure user/group exists locally in company DB before writing permissions
                                string ensureLocalSubjectQuery = @"
                                     IF NOT EXISTS (SELECT 1 FROM SegUserGrp WHERE idSegUserGrp = @idUserGrp)
                                     BEGIN
                                         INSERT INTO SegUserGrp (idSegUserGrp, Clave, esGrupo, ObjetoDefault, Activo, Nivel, rowguid)
                                         SELECT idSegUserGrp, Clave, esGrupo, ObjetoDefault, Activo, Nivel, GuidUserGrp
                                         FROM CBSRepository..SegUserGrp
                                         WHERE idSegUserGrp = @idUserGrp
                                     END";
                                using (var cmd = new SqlCommand(ensureLocalSubjectQuery, conn, transaction))
                                {
                                    cmd.Parameters.AddWithValue("@idUserGrp", p.IdSegUserGrp);
                                    cmd.ExecuteNonQuery();
                                }

                                string upsertQuery = @"
                                    IF EXISTS (SELECT 1 FROM SegPermiso WHERE idSegObjeto = @idObj AND idSegUserGrp = @idUserGrp)
                                    BEGIN
                                        UPDATE SegPermiso SET 
                                            Agregar = @Agregar, Editar = @Editar, Borrar = @Borrar, 
                                            Imprimir = @Imprimir, Abrir = @Abrir, Anular = @Anular, Aprobar = @Aprobar
                                        WHERE idSegObjeto = @idObj AND idSegUserGrp = @idUserGrp
                                    END
                                    ELSE
                                    BEGIN
                                        INSERT INTO SegPermiso (idSegObjeto, idSegUserGrp, Agregar, Editar, Borrar, Imprimir, Abrir, Anular, Aprobar, rowguid)
                                        VALUES (@idObj, @idUserGrp, @Agregar, @Editar, @Borrar, @Imprimir, @Abrir, @Anular, @Aprobar, NEWID())
                                    END";

                                using (var cmd = new SqlCommand(upsertQuery, conn, transaction))
                                {
                                    cmd.Parameters.AddWithValue("@idObj", p.IdSegObjeto);
                                    cmd.Parameters.AddWithValue("@idUserGrp", p.IdSegUserGrp);
                                    cmd.Parameters.AddWithValue("@Agregar", p.Agregar);
                                    cmd.Parameters.AddWithValue("@Editar", p.Editar);
                                    cmd.Parameters.AddWithValue("@Borrar", p.Borrar);
                                    cmd.Parameters.AddWithValue("@Imprimir", p.Imprimir);
                                    cmd.Parameters.AddWithValue("@Abrir", p.Abrir);
                                    cmd.Parameters.AddWithValue("@Anular", p.Anular);
                                    cmd.Parameters.AddWithValue("@Aprobar", p.Aprobar);
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
                return Ok("Permisos actualizados exitosamente.");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al guardar matriz de permisos: {ex.Message}");
            }
        }

        [HttpPost("check")]
        public IActionResult CheckPermission([FromBody] PermissionDto request)
        {
            string username = User.Identity?.Name;
            if (string.IsNullOrEmpty(username))
            {
                return Unauthorized();
            }

            if (request == null || string.IsNullOrEmpty(request.IdSegObjeto) || string.IsNullOrEmpty(request.SegObjeto))
            {
                return BadRequest("Objeto y acción a verificar son requeridos.");
            }

            string connStr = GetCompanyConnectionString();
            if (string.IsNullOrEmpty(connStr))
            {
                return BadRequest("No ha seleccionado ninguna empresa activa.");
            }

            try
            {
                int userNivel = 3;
                var nivelClaim = User.FindFirst("Nivel");
                if (nivelClaim != null)
                {
                    int.TryParse(nivelClaim.Value, out userNivel);
                }

                byte acceso = 0;
                using (var conn = _databaseService.GetCompanyConnection(connStr))
                {
                    conn.Open();
                    using (var cmd = new SqlCommand("Permisos", conn))
                    {
                        cmd.CommandType = CommandType.StoredProcedure;
                        cmd.Parameters.AddWithValue("@User", username);
                        cmd.Parameters.AddWithValue("@Objeto", request.IdSegObjeto);

                        using (var reader = cmd.ExecuteReader())
                        {
                            if (reader.Read())
                            {
                                // We check the specific permission column requested
                                string action = request.SegObjeto.ToLower();
                                string columnName = action switch
                                {
                                    "abrir" => "Abrir",
                                    "agregar" => "Agregar",
                                    "editar" => "Editar",
                                    "borrar" => "Borrar",
                                    "imprimir" => "Imprimir",
                                    "anular" => "Anular",
                                    "aprobar" => "Aprobar",
                                    _ => "Abrir"
                                };
                                acceso = reader.GetByte(reader.GetOrdinal(columnName));
                            }
                        }
                    }
                }

                // If no permissions defined (acceso = 0), denegado
                if (acceso == 0)
                {
                    return Ok(new { Allowed = false, RequireOverride = false, Message = "Permiso denegado por políticas de seguridad." });
                }

                // If acceso is 6 (open access) or user clearance is enough, allowed
                if (acceso == 6 || acceso <= userNivel)
                {
                    return Ok(new { Allowed = true, RequireOverride = false, Message = "Permiso concedido." });
                }

                // If user clearance is not enough, require supervisor override
                return Ok(new
                {
                    Allowed = false,
                    RequireOverride = true,
                    RequiredClass = acceso,
                    Message = $"La acción requiere autorización de un supervisor de nivel {acceso} o superior."
                });
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al verificar permisos: {ex.Message}");
            }
        }

        [HttpPost("authorize")]
        public IActionResult AuthorizeOverride([FromBody] OverrideRequest request)
        {
            string username = User.Identity?.Name;
            if (string.IsNullOrEmpty(username))
            {
                return Unauthorized();
            }

            if (request == null || string.IsNullOrEmpty(request.Clave) || request.Clase <= 0)
            {
                return BadRequest("Clave de token y nivel requerido son necesarios.");
            }

            string connStr = GetCompanyConnectionString();
            if (string.IsNullOrEmpty(connStr))
            {
                return BadRequest("No ha seleccionado ninguna empresa activa.");
            }

            try
            {
                bool isAuthorized = false;
                using (var conn = _databaseService.GetCompanyConnection(connStr))
                {
                    conn.Open();
                    using (var cmd = new SqlCommand("AutorizacionChk", conn))
                    {
                        cmd.CommandType = CommandType.StoredProcedure;
                        cmd.Parameters.AddWithValue("@idAutorizacion", request.Clave);
                        cmd.Parameters.AddWithValue("@Clase", request.Clase);
                        cmd.Parameters.AddWithValue("@Referencia", request.Referencia ?? "");
                        cmd.Parameters.AddWithValue("@Usadopor", username);
                        cmd.Parameters.AddWithValue("@Descripcion", request.Descripcion ?? "");

                        var okParam = new SqlParameter("@OK", SqlDbType.Bit)
                        {
                            Direction = ParameterDirection.Output
                        };
                        cmd.Parameters.Add(okParam);

                        cmd.ExecuteNonQuery();
                        
                        isAuthorized = okParam.Value != DBNull.Value && (bool)okParam.Value;
                    }
                }

                if (isAuthorized)
                {
                    return Ok(new { Authorized = true, Message = "Autorización del supervisor validada y consumida con éxito." });
                }
                else
                {
                    return BadRequest("La clave de autorización es inválida, tiene nivel inferior al requerido, o ya fue consumida.");
                }
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al procesar autorización: {ex.Message}");
            }
        }
    }
}
