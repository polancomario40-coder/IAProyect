using System.Text.Json;
using ControlPuertaAPI.Models;
using Microsoft.Data.SqlClient;

namespace ControlPuertaAPI.Services;

/// <summary>
/// Servicio de evidencias: guarda y recupera fotos, firmas y documentos
/// en la base de datos independiente SADE_Evidencias.
/// Cross-BD linkado por GUID (idEvidencia) en AdelH.
/// </summary>
public interface IEvidenciaService
{
    Task<Guid> GuardarEvidenciaAsync(
        Guid    idRefExterna,
        string  referencia,
        string? fotoConduceBase64,
        string? fotoConduceMime,
        string? fotoConduceNombre,
        string? firmaDigitalBase64,
        string? imagenFirmadaBase64,
        string? fotoCamionBase64,
        object? metadatos,
        string  usuario,
        string? ip);

    Task<(byte[]? fotoConduce, byte[]? firmaDigital, byte[]? imagenFirmada, byte[]? fotoCamion)>
        ObtenerBinariosAsync(Guid idEvidencia);
}

public class EvidenciaService : IEvidenciaService
{
    private readonly IConnectionFactory _cf;
    private readonly ILogger<EvidenciaService> _logger;

    public EvidenciaService(IConnectionFactory cf, ILogger<EvidenciaService> logger)
    {
        _cf     = cf;
        _logger = logger;
    }

    public async Task<Guid> GuardarEvidenciaAsync(
        Guid    idRefExterna,
        string  referencia,
        string? fotoConduceBase64,
        string? fotoConduceMime,
        string? fotoConduceNombre,
        string? firmaDigitalBase64,
        string? imagenFirmadaBase64,
        string? fotoCamionBase64,
        object? metadatos,
        string  usuario,
        string? ip)
    {
        var idEvidencia      = Guid.NewGuid();
        var fotoConduce      = Base64ToBytes(fotoConduceBase64);
        var firmaDigital     = Base64ToBytes(firmaDigitalBase64);
        var imagenFirmada    = Base64ToBytes(imagenFirmadaBase64);
        var fotoCamion       = Base64ToBytes(fotoCamionBase64);
        var metadatosJson    = metadatos is null ? null : JsonSerializer.Serialize(metadatos);

        await using var conn = _cf.CreateEvidenciasConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText  = "evGuardarEvidencia";
        cmd.CommandType  = System.Data.CommandType.StoredProcedure;

        cmd.Parameters.AddWithValue("@idEvidencia",         idEvidencia);
        cmd.Parameters.AddWithValue("@idRefExterna",        idRefExterna);
        cmd.Parameters.AddWithValue("@Referencia",          referencia);
        AddBinaryParam(cmd, "@FotoConduce",      fotoConduce);
        cmd.Parameters.AddWithValue("@FotoConduceMime",     (object?)fotoConduceMime    ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@FotoConduceNombre",   (object?)fotoConduceNombre  ?? DBNull.Value);
        AddBinaryParam(cmd, "@FirmaDigital",     firmaDigital);
        AddBinaryParam(cmd, "@ImagenFirmada",    imagenFirmada);
        AddBinaryParam(cmd, "@FotoCamion",       fotoCamion);
        cmd.Parameters.AddWithValue("@Metadatos",           (object?)metadatosJson      ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@Usuario",             usuario);
        cmd.Parameters.AddWithValue("@IpOrigen",            (object?)ip                 ?? DBNull.Value);

        await cmd.ExecuteNonQueryAsync();
        _logger.LogInformation("[EVIDENCIA] Guardada idEvidencia={Id} para conduce {Ref}", idEvidencia, referencia);
        return idEvidencia;
    }

    public async Task<(byte[]? fotoConduce, byte[]? firmaDigital, byte[]? imagenFirmada, byte[]? fotoCamion)>
        ObtenerBinariosAsync(Guid idEvidencia)
    {
        await using var conn = _cf.CreateEvidenciasConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT FotoConduce, FirmaDigital, ImagenFirmada, FotoCamion FROM Evidencias WHERE idEvidencia = @id";
        cmd.Parameters.AddWithValue("@id", idEvidencia);

        await using var reader = await cmd.ExecuteReaderAsync();
        if (!await reader.ReadAsync())
            return (null, null, null, null);

        return (
            reader.IsDBNull(0) ? null : (byte[])reader[0],
            reader.IsDBNull(1) ? null : (byte[])reader[1],
            reader.IsDBNull(2) ? null : (byte[])reader[2],
            reader.IsDBNull(3) ? null : (byte[])reader[3]
        );
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static byte[]? Base64ToBytes(string? base64)
    {
        if (string.IsNullOrWhiteSpace(base64)) return null;
        // Eliminar prefijo data URI si existe (data:image/jpeg;base64,...)
        var idx = base64.IndexOf(',');
        var clean = idx >= 0 ? base64[(idx + 1)..] : base64;
        return Convert.FromBase64String(clean);
    }

    private static void AddBinaryParam(SqlCommand cmd, string name, byte[]? value)
    {
        var param = cmd.Parameters.Add(name, System.Data.SqlDbType.VarBinary, -1);
        param.Value = (object?)value ?? DBNull.Value;
    }
}
