using System;
using System.Collections.Generic;
using System.Data;
using System.Text.Json;
using System.Threading.Tasks;
using Dapper;
using Microsoft.Data.SqlClient;
using Microsoft.Extensions.Configuration;
using SADE_DashboardAPI.Models;

namespace SADE_DashboardAPI.Services
{
    public class DashboardService : IDashboardService
    {
        private readonly SADE_DashboardAPI.Providers.IErpConnectionProvider _connectionProvider;
        private readonly Microsoft.AspNetCore.Http.IHttpContextAccessor _httpContextAccessor;

        public DashboardService(SADE_DashboardAPI.Providers.IErpConnectionProvider connectionProvider, Microsoft.AspNetCore.Http.IHttpContextAccessor httpContextAccessor)
        {
            _connectionProvider = connectionProvider;
            _httpContextAccessor = httpContextAccessor;
        }

        public async Task<IEnumerable<dynamic>> GetDashboardMenuAsync()
        {
            var connectionString = await _connectionProvider.GetConnectionStringAsync();
            using var connection = new SqlConnection(connectionString);
            var query = "SELECT Id, Nombre, Modulo FROM SADE_SYS_DashboardConfig ORDER BY Modulo, Nombre";
            return await connection.QueryAsync(query);
        }

        public async Task<DashboardResponse> GetDashboardDataAsync(int idIndicador, DateTime fechaDesde, DateTime fechaHasta)
        {
            var connectionString = await _connectionProvider.GetConnectionStringAsync();
            using var connection = new SqlConnection(connectionString);

            // 1. Obtener la meta-configuración visual
            var queryConfig = "SELECT Id, Nombre, Modulo, TipoVista, ProcedimientoSQL, EjeX, EjeY, ConfiguracionUI FROM SADE_SYS_DashboardConfig WHERE Id = @Id";
            var config = await connection.QueryFirstOrDefaultAsync<DashboardConfig>(queryConfig, new { Id = idIndicador });

            if (config == null)
            {
                return null; // o lanzar excepción, el controlador manejará el 404
            }

            // Parsear ConfiguracionUI de string a objeto dinámico
            dynamic? configUIObj = null;
            if (!string.IsNullOrWhiteSpace(config.ConfiguracionUI))
            {
                try
                {
                    configUIObj = JsonSerializer.Deserialize<dynamic>(config.ConfiguracionUI);
                }
                catch
                {
                    // Si falla el parseo, lo dejamos como string u objeto anónimo con error
                    configUIObj = new { error = "Invalid JSON in ConfiguracionUI", originalString = config.ConfiguracionUI };
                }
            }

            // Construir metadata combinada
            var metadata = new 
            {
                config.Id,
                config.Nombre,
                config.Modulo,
                config.TipoVista,
                config.EjeX,
                config.EjeY,
                ConfiguracionUI = configUIObj
            };

            // 2. Ejecutar dinámicamente el Stored Procedure
            IEnumerable<dynamic> data = new List<dynamic>();
            if (!string.IsNullOrWhiteSpace(config.ProcedimientoSQL))
            {
                // Para evitar errores de "Too many arguments" o nombres diferentes (@Desde vs @FechaDesde),
                // primero consultamos qué parámetros pide realmente este Stored Procedure.
                var spParamsQuery = @"
                    SELECT p.name AS ParamName 
                    FROM sys.parameters p
                    INNER JOIN sys.procedures pr ON p.object_id = pr.object_id
                    WHERE pr.name = PARSENAME(@SpName, 1)";
                    
                var expectedParams = await connection.QueryAsync<string>(spParamsQuery, new { SpName = config.ProcedimientoSQL });
                
                var dynamicParams = new DynamicParameters();
                
                // Mapear dinámicamente según lo que pide el SP
                foreach (var param in expectedParams)
                {
                    var cleanName = param.Replace("@", "").ToLower();
                    if (cleanName == "fechadesde" || cleanName == "desde" || cleanName == "inicial")
                    {
                        dynamicParams.Add(param, fechaDesde);
                    }
                    else if (cleanName == "fechahasta" || cleanName == "hasta" || cleanName == "fechacorte" || cleanName == "fecha" || cleanName == "final")
                    {
                        dynamicParams.Add(param, fechaHasta);
                    }
                    else if (cleanName == "idempresa" || cleanName == "empresa" || cleanName == "empid")
                    {
                        var httpContext = _httpContextAccessor.HttpContext;
                        var empIdHeader = httpContext?.Request.Headers["X-Selected-Company"].ToString();
                        
                        // Si no hay header, o no hay contexto, fallamos a "1" por seguridad (aunque AuthGuard lo evitará en UI)
                        var finalEmpId = string.IsNullOrWhiteSpace(empIdHeader) ? "1" : empIdHeader;
                        dynamicParams.Add(param, finalEmpId); 
                    }
                }

                data = await connection.QueryAsync(config.ProcedimientoSQL, dynamicParams, commandType: CommandType.StoredProcedure);
            }

            return new DashboardResponse
            {
                Metadata = metadata,
                Data = data
            };
        }
    }
}
