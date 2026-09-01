using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Authorization;
using Microsoft.EntityFrameworkCore;
using CuadreApi.Data;
using CuadreApi.Models;
using System;
using System.Collections.Generic;
using System.Security.Claims;
using System.Threading.Tasks;
using System.Linq;

namespace CuadreApi.Controllers;

[Authorize]
[ApiController]
[Route("api/[controller]")]
public class CuadreController : ControllerBase
{
    private readonly CuadreDbContext _context;
    private readonly AuthDbContext _authDb;

    public CuadreController(CuadreDbContext context, AuthDbContext authDb)
    {
        _context = context;
        _authDb = authDb;
    }

    [HttpGet]
    public async Task<IActionResult> GetCuadre(
        [FromQuery] DateTime desde, 
        [FromQuery] DateTime hasta, 
        [FromQuery] string? usuario, 
        [FromQuery] string? sucursal)
    {
        var sub = User.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value 
                  ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value 
                  ?? User.FindFirst(ClaimTypes.Name)?.Value 
                  ?? "";

        // Ajustar fecha 'hasta' para que incluya todo el dia (23:59:59)
        hasta = hasta.Date.AddDays(1).AddSeconds(-1);

        Console.WriteLine($"[CUADRE QUERY] UserToken: '{sub}', QueryUser: '{usuario}', Desde: '{desde}', Hasta: '{hasta}', Sucursal: '{sucursal}'");
        
        var records = new List<SpCuadre>();

        try
        {
            var connection = _context.Database.GetDbConnection();
            await _context.Database.OpenConnectionAsync();

            using (var command = connection.CreateCommand())
            {
                // Mapped to svCuadreUsuario stored procedure in SAEExpress / Selected ERP database
                command.CommandText = "dbo.svCuadreUsuario";
                command.CommandType = System.Data.CommandType.StoredProcedure;

                var pDesde = command.CreateParameter();
                pDesde.ParameterName = "@desde";
                pDesde.Value = desde;
                command.Parameters.Add(pDesde);

                var pHasta = command.CreateParameter();
                pHasta.ParameterName = "@hasta";
                pHasta.Value = hasta;
                command.Parameters.Add(pHasta);

                var pUsuario = command.CreateParameter();
                pUsuario.ParameterName = "@usuario";
                // If a specific user is selected (and not "Todos" or empty), filter by it.
                // Otherwise pass DBNull.Value to return all users.
                pUsuario.Value = string.IsNullOrEmpty(usuario) || usuario.Equals("Todos", StringComparison.OrdinalIgnoreCase)
                                 ? DBNull.Value 
                                 : usuario.Trim();
                command.Parameters.Add(pUsuario);

                var pSucursal = command.CreateParameter();
                pSucursal.ParameterName = "@Sucursal";
                
                string finalSucursal = sucursal;
                if (!string.IsNullOrEmpty(sucursal) && !sucursal.Equals("Todos", StringComparison.OrdinalIgnoreCase))
                {
                    // Resolve idCentroCosto (GUID) to idAlmacen to maintain compatibility with svCuadreUsuario
                    using (var resolveCmd = connection.CreateCommand())
                    {
                        resolveCmd.CommandText = "SELECT TOP 1 a.idAlmacen FROM CentroCosto cc INNER JOIN Almacen a ON cc.CentroCosto = a.idAlmacen WHERE cc.idCentroCosto = @ccId";
                        var pId = resolveCmd.CreateParameter();
                        pId.ParameterName = "@ccId";
                        pId.Value = sucursal;
                        resolveCmd.Parameters.Add(pId);
                        
                        var result = await resolveCmd.ExecuteScalarAsync();
                        if (result != null && result != DBNull.Value)
                        {
                            finalSucursal = result.ToString();
                        }
                    }
                }

                pSucursal.Value = string.IsNullOrEmpty(finalSucursal) || finalSucursal.Equals("Todos", StringComparison.OrdinalIgnoreCase)
                                  ? DBNull.Value 
                                  : finalSucursal.Trim();
                command.Parameters.Add(pSucursal);

                using (var reader = await command.ExecuteReaderAsync())
                {
                    while (await reader.ReadAsync())
                    {
                        records.Add(new SpCuadre
                        {
                            Sucursal = reader["Sucursal"] != DBNull.Value ? reader["Sucursal"]?.ToString()?.Trim() : null,
                            Orden = reader["orden"] != DBNull.Value ? Convert.ToInt32(reader["orden"]) : 1,
                            Usuario = reader["Usuario"] != DBNull.Value ? reader["Usuario"]?.ToString()?.Trim() : null,
                            Idfactura = reader["idfactura"] != DBNull.Value ? (Guid)reader["idfactura"] : null,
                            Registro = reader["Registro"] != DBNull.Value ? reader["Registro"]?.ToString()?.Trim() : null,
                            Numero = reader["Numero"] != DBNull.Value ? reader["Numero"]?.ToString()?.Trim() : null,
                            Cliente = reader["Cliente"] != DBNull.Value ? reader["Cliente"]?.ToString()?.Trim() : null,
                            Fecha = reader["fecha"] != DBNull.Value ? (DateTime)reader["fecha"] : null,
                            Moneda = reader["Moneda"] != DBNull.Value ? reader["Moneda"]?.ToString()?.Trim() : null,
                            Efectivo = reader["Efectivo"] != DBNull.Value ? Convert.ToDecimal(reader["Efectivo"]) : 0,
                            Tarjeta = reader["Tarjeta"] != DBNull.Value ? Convert.ToDecimal(reader["Tarjeta"]) : 0,
                            Cheque = reader["Cheque"] != DBNull.Value ? Convert.ToDecimal(reader["Cheque"]) : 0,
                            Otros = reader["Otros"] != DBNull.Value ? Convert.ToDecimal(reader["Otros"]) : 0,
                            Credito = reader["Credito"] != DBNull.Value ? Convert.ToDecimal(reader["Credito"]) : null,
                            Factura = reader["Factura"] != DBNull.Value ? Convert.ToDecimal(reader["Factura"]) : 0,
                            Recibos = reader["Recibos"] != DBNull.Value ? Convert.ToDecimal(reader["Recibos"]) : 0,
                            Gastos = reader["Gastos"] != DBNull.Value ? Convert.ToDecimal(reader["Gastos"]) : 0
                        });
                    }
                }
            }

            Console.WriteLine($"[CUADRE QUERY RESULT] Found {records.Count} records.");
            return Ok(records);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[CUADRE API ERROR]: {ex.Message}");
            Console.WriteLine($"[CUADRE API INNER ERROR]: {ex.InnerException?.Message}");
            return StatusCode(500, new { mensaje = $"Error al consultar cuadre de caja en base de datos: {ex.Message}" });
        }
        finally
        {
            await _context.Database.CloseConnectionAsync();
        }
    }

    [HttpGet("sucursales")]
    public async Task<IActionResult> GetSucursales()
    {
        try
        {
            var sucursales = new List<object>();
            var connection = _context.Database.GetDbConnection();
            await _context.Database.OpenConnectionAsync();

            using (var command = connection.CreateCommand())
            {
                command.CommandText = "dbo.CuadreSucursales";
                command.CommandType = System.Data.CommandType.StoredProcedure;
                    
                using (var reader = await command.ExecuteReaderAsync())
                {
                    while (await reader.ReadAsync())
                    {
                        sucursales.Add(new
                        {
                            IdSucursal = reader["idCentroCosto"]?.ToString()?.Trim(),
                            Sucursal = reader["CentroCosto"]?.ToString()?.Trim()
                        });
                    }
                }
            }

            return Ok(sucursales);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[CUADRE API ERROR SUCURSALES]: {ex.Message}");
            return StatusCode(500, new { mensaje = $"Error al obtener sucursales: {ex.Message}" });
        }
        finally
        {
            await _context.Database.CloseConnectionAsync();
        }
    }

    [HttpGet("cajeros")]
    public async Task<IActionResult> GetCajeros()
    {
        try
        {
            var cajeros = new List<object>();
            cajeros.Add(new { Usuario = "Todos", Nombre = "Todos" });
            var connection = _context.Database.GetDbConnection();
            await _context.Database.OpenConnectionAsync();

            using (var command = connection.CreateCommand())
            {
                command.CommandText = "dbo.CuadreCajero";
                command.CommandType = System.Data.CommandType.StoredProcedure;
                    
                using (var reader = await command.ExecuteReaderAsync())
                {
                    while (await reader.ReadAsync())
                    {
                        var usr = reader["idSegUsergrp"] != DBNull.Value ? reader["idSegUsergrp"]?.ToString()?.Trim() : "Todos";
                        var nom = reader["Nombre"]?.ToString()?.Trim();
                        if (!string.IsNullOrEmpty(nom))
                        {
                            cajeros.Add(new { Usuario = usr, Nombre = nom });
                        }
                    }
                }
            }

            return Ok(cajeros);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[CUADRE API ERROR CAJEROS]: {ex.Message}");
            return StatusCode(500, new { mensaje = $"Error al obtener cajeros: {ex.Message}" });
        }
        finally
        {
            await _context.Database.CloseConnectionAsync();
        }
    }
}
