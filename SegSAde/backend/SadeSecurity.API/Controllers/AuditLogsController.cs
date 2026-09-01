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
    public class AuditLogsController : ControllerBase
    {
        private readonly IDatabaseService _databaseService;

        public AuditLogsController(IDatabaseService databaseService)
        {
            _databaseService = databaseService;
        }

        private Guid GetCompanyId()
        {
            var claim = User.FindFirst("CompanyId");
            return claim != null ? Guid.Parse(claim.Value) : Guid.Empty;
        }

        [HttpGet]
        public IActionResult GetLogs()
        {
            Guid companyId = GetCompanyId();
            if (companyId == Guid.Empty)
            {
                return BadRequest("No ha seleccionado ninguna empresa activa.");
            }

            try
            {
                var list = new List<AuditLogDto>();
                using (var conn = _databaseService.GetRepositoryConnection())
                {
                    conn.Open();
                    
                    // Select the latest 200 security logs for this company or global logs (companyId = null)
                    string query = @"
                        SELECT TOP 200 
                            idLog, idEmpresa, fechaHora, Usuario, Estacion, Evento, Objeto, Referencia, Descripcion, DatosAdicionales
                        FROM segLog 
                        WHERE idEmpresa = @idEmpresa OR idEmpresa IS NULL
                        ORDER BY fechaHora DESC";

                    using (var cmd = new SqlCommand(query, conn))
                    {
                        cmd.Parameters.AddWithValue("@idEmpresa", companyId);
                        using (var reader = cmd.ExecuteReader())
                        {
                            while (reader.Read())
                            {
                                list.Add(new AuditLogDto
                                {
                                    IdLog = reader.GetGuid(0),
                                    IdEmpresa = reader.IsDBNull(1) ? Guid.Empty : reader.GetGuid(1),
                                    FechaHora = reader.GetDateTime(2),
                                    Usuario = reader.IsDBNull(3) ? "" : reader.GetString(3),
                                    Estacion = reader.IsDBNull(4) ? "" : reader.GetString(4),
                                    Evento = reader.IsDBNull(5) ? "" : reader.GetString(5),
                                    Objeto = reader.IsDBNull(6) ? "" : reader.GetString(6),
                                    Referencia = reader.IsDBNull(7) ? "" : reader.GetString(7),
                                    Descripcion = reader.IsDBNull(8) ? "" : reader.GetString(8),
                                    DatosAdicionales = reader.IsDBNull(9) ? "" : reader.GetString(9)
                                });
                            }
                        }
                    }
                }
                return Ok(list);
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al obtener logs de auditoría: {ex.Message}");
            }
        }
    }
}
