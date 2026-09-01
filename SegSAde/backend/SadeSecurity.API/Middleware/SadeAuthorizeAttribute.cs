using System;
using System.Data;
using System.Security.Claims;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Filters;
using Microsoft.Data.SqlClient;
using SadeSecurity.API.Services;

namespace SadeSecurity.API.Middleware
{
    public enum SadePermission
    {
        Abrir,
        Agregar,
        Editar,
        Borrar,
        Imprimir,
        Anular,
        Aprobar
    }

    [AttributeUsage(AttributeTargets.Method | AttributeTargets.Class)]
    public class SadeAuthorizeAttribute : Attribute, IAuthorizationFilter
    {
        public string ObjectName { get; set; } = string.Empty;
        public SadePermission Permission { get; set; } = SadePermission.Abrir;

        public void OnAuthorization(AuthorizationFilterContext context)
        {
            var user = context.HttpContext.User;
            if (user == null || user.Identity == null || !user.Identity.IsAuthenticated)
            {
                context.Result = new UnauthorizedResult();
                return;
            }

            string username = user.Identity.Name ?? "";
            
            // 1. Get company connection string from claims
            var connStringClaim = user.FindFirst("CompanyConnString");
            if (connStringClaim == null || string.IsNullOrEmpty(connStringClaim.Value))
            {
                context.Result = new JsonResult(new { message = "Se requiere seleccionar una empresa activa primero." })
                {
                    StatusCode = 401
                };
                return;
            }

            string connStr = connStringClaim.Value;

            // 2. Get user clearance level from claims
            int userNivel = 3;
            var nivelClaim = user.FindFirst("Nivel");
            if (nivelClaim != null)
            {
                int.TryParse(nivelClaim.Value, out userNivel);
            }

            try
            {
                // We resolve DatabaseService using HttpContext Services (Dependency Injection)
                var dbService = (IDatabaseService)context.HttpContext.RequestServices.GetService(typeof(IDatabaseService))!;
                
                byte acceso = 0;
                using (var conn = dbService.GetCompanyConnection(connStr))
                {
                    conn.Open();
                    using (var cmd = new SqlCommand("Permisos", conn))
                    {
                        cmd.CommandType = CommandType.StoredProcedure;
                        cmd.Parameters.AddWithValue("@User", username);
                        cmd.Parameters.AddWithValue("@Objeto", ObjectName);

                        using (var reader = cmd.ExecuteReader())
                        {
                            if (reader.Read())
                            {
                                string columnName = Permission.ToString();
                                acceso = reader.GetByte(reader.GetOrdinal(columnName));
                            }
                        }
                    }
                }

                // If acceso is 0 (denegado), fail authorization
                if (acceso == 0)
                {
                    context.Result = new JsonResult(new { allowed = false, message = "Acceso denegado. No tiene permisos para esta acción." })
                    {
                        StatusCode = 403
                    };
                    return;
                }

                // If acceso is 6 (open) or user has enough clearance, succeed
                if (acceso == 6 || acceso <= userNivel)
                {
                    return; // Authorized, continue request execution
                }

                // Otherwise, clearance is insufficient, require supervisor override
                context.Result = new JsonResult(new 
                { 
                    allowed = false, 
                    requireOverride = true, 
                    requiredClass = acceso,
                    message = $"Nivel de autorización insuficiente. Se requiere autorización de clase {acceso}." 
                })
                {
                    StatusCode = 403
                };
            }
            catch (Exception ex)
            {
                context.Result = new JsonResult(new { message = $"Error de autorización interna: {ex.Message}" })
                {
                    StatusCode = 500
                };
            }
        }
    }
}
