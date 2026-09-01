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
    public class CompaniesController : ControllerBase
    {
        private readonly IDatabaseService _databaseService;
        private readonly ICryptoService _cryptoService;

        public CompaniesController(IDatabaseService databaseService, ICryptoService cryptoService)
        {
            _databaseService = databaseService;
            _cryptoService = cryptoService;
        }

        [HttpGet]
        public IActionResult GetCompanies()
        {
            try
            {
                var list = new List<CompanyDto>();
                using (var conn = _databaseService.GetRepositoryConnection())
                {
                    conn.Open();
                    string query = "SELECT idEmpresa, Empresa, RNC, Servidor, BaseDatos, Trusted, UserId, UserPwd, Activa FROM cfgEmpresa ORDER BY Empresa";
                    using (var cmd = new SqlCommand(query, conn))
                    {
                        using (var reader = cmd.ExecuteReader())
                        {
                            while (reader.Read())
                            {
                                string encPwd = reader.IsDBNull(7) ? "" : reader.GetString(7);
                                // We don't return the raw password to the client, we return a placeholder or decrypted if needed.
                                // But for safety, we return empty password unless explicitly updating.
                                list.Add(new CompanyDto
                                {
                                    IdEmpresa = reader.GetGuid(0),
                                    Empresa = reader.GetString(1),
                                    RNC = reader.IsDBNull(2) ? "" : reader.GetString(2),
                                    Servidor = reader.IsDBNull(3) ? "" : reader.GetString(3),
                                    BaseDatos = reader.IsDBNull(4) ? "" : reader.GetString(4),
                                    Trusted = reader.IsDBNull(5) ? false : reader.GetBoolean(5),
                                    UserId = reader.IsDBNull(6) ? "" : reader.GetString(6),
                                    UserPwd = string.IsNullOrEmpty(encPwd) ? "" : "********",
                                    Activa = reader.IsDBNull(8) ? false : reader.GetBoolean(8)
                                });
                            }
                        }
                    }
                }
                return Ok(list);
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al obtener empresas: {ex.Message}");
            }
        }

        [HttpPost]
        public IActionResult CreateCompany([FromBody] CompanyDto company)
        {
            if (company == null || string.IsNullOrEmpty(company.Empresa) || string.IsNullOrEmpty(company.BaseDatos))
            {
                return BadRequest("Nombre de empresa y base de datos son necesarios.");
            }

            try
            {
                Guid companyGuid = Guid.NewGuid();
                string encryptedPwd = "";
                string encryptedUser = "";
                
                if (!company.Trusted)
                {
                    encryptedUser = _cryptoService.EncryptString(company.UserId);
                    encryptedPwd = _cryptoService.EncryptString(company.UserPwd);
                }

                using (var conn = _databaseService.GetRepositoryConnection())
                {
                    conn.Open();
                    string query = @"
                        INSERT INTO cfgEmpresa (idEmpresa, Empresa, RNC, Servidor, BaseDatos, Trusted, UserId, UserPwd, Activa, HacerBackup, Encriptada, accesoWeb)
                        VALUES (@id, @Empresa, @RNC, @Servidor, @BaseDatos, @Trusted, @UserId, @UserPwd, @Activa, 1, 1, 1)";

                    using (var cmd = new SqlCommand(query, conn))
                    {
                        cmd.Parameters.AddWithValue("@id", companyGuid);
                        cmd.Parameters.AddWithValue("@Empresa", company.Empresa);
                        cmd.Parameters.AddWithValue("@RNC", company.RNC ?? "");
                        cmd.Parameters.AddWithValue("@Servidor", company.Servidor ?? "");
                        cmd.Parameters.AddWithValue("@BaseDatos", company.BaseDatos);
                        cmd.Parameters.AddWithValue("@Trusted", company.Trusted);
                        cmd.Parameters.AddWithValue("@UserId", encryptedUser);
                        cmd.Parameters.AddWithValue("@UserPwd", encryptedPwd);
                        cmd.Parameters.AddWithValue("@Activa", company.Activa);
                        cmd.ExecuteNonQuery();
                    }
                }

                return Ok("Empresa registrada exitosamente.");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al registrar empresa: {ex.Message}");
            }
        }

        [HttpPut("{companyId}")]
        public IActionResult UpdateCompany(Guid companyId, [FromBody] CompanyDto company)
        {
            if (company == null || companyId == Guid.Empty)
            {
                return BadRequest("Datos de empresa inválidos.");
            }

            try
            {
                using (var conn = _databaseService.GetRepositoryConnection())
                {
                    conn.Open();

                    string query = @"
                        UPDATE cfgEmpresa SET 
                            Empresa = @Empresa, RNC = @RNC, Servidor = @Servidor, 
                            BaseDatos = @BaseDatos, Trusted = @Trusted, Activa = @Activa";

                    bool updatePassword = !company.Trusted && !string.IsNullOrEmpty(company.UserPwd) && company.UserPwd != "********";
                    if (updatePassword)
                    {
                        query += ", UserId = @UserId, UserPwd = @UserPwd, Encriptada = 1";
                    }
                    else if (!company.Trusted)
                    {
                        query += ", UserId = @UserId";
                    }

                    query += " WHERE idEmpresa = @id";

                    using (var cmd = new SqlCommand(query, conn))
                    {
                        cmd.Parameters.AddWithValue("@id", companyId);
                        cmd.Parameters.AddWithValue("@Empresa", company.Empresa);
                        cmd.Parameters.AddWithValue("@RNC", company.RNC ?? "");
                        cmd.Parameters.AddWithValue("@Servidor", company.Servidor ?? "");
                        cmd.Parameters.AddWithValue("@BaseDatos", company.BaseDatos);
                        cmd.Parameters.AddWithValue("@Trusted", company.Trusted);
                        cmd.Parameters.AddWithValue("@Activa", company.Activa);

                        if (!company.Trusted)
                        {
                            string encryptedUser = _cryptoService.EncryptString(company.UserId);
                            cmd.Parameters.AddWithValue("@UserId", encryptedUser);
                            
                            if (updatePassword)
                            {
                                string encryptedPwd = _cryptoService.EncryptString(company.UserPwd);
                                cmd.Parameters.AddWithValue("@UserPwd", encryptedPwd);
                            }
                        }

                        cmd.ExecuteNonQuery();
                    }
                }

                return Ok("Empresa actualizada exitosamente.");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al actualizar empresa: {ex.Message}");
            }
        }

        [HttpDelete("{companyId}")]
        public IActionResult DeleteCompany(Guid companyId)
        {
            if (companyId == Guid.Empty)
            {
                return BadRequest("Identificador de empresa inválido.");
            }

            try
            {
                using (var conn = _databaseService.GetRepositoryConnection())
                {
                    conn.Open();
                    using (var cmd = new SqlCommand("UPDATE cfgEmpresa SET Activa = 0 WHERE idEmpresa = @id", conn))
                    {
                        cmd.Parameters.AddWithValue("@id", companyId);
                        cmd.ExecuteNonQuery();
                    }
                }
                return Ok("Empresa desactivada exitosamente.");
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Error al eliminar empresa: {ex.Message}");
            }
        }
    }
}
