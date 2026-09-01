using ControlPuertaAPI.Models;
using Microsoft.Data.SqlClient;

namespace ControlPuertaAPI.Services;

/// <summary>
/// Servicio de acceso a datos para la BD AdelH (ERP SADE).
/// Usa Microsoft.Data.SqlClient directamente (sin ORM) igual que los demás módulos.
/// Encapsula todos los queries relacionados con prtEntradaCamion, lgTransportista,
/// lgTransportistaEquipo y ocOrdenes.
/// </summary>
public interface IPuertaDbService
{
    Task<TransportistaDto?> BuscarTransportistaPorPlacaAsync(string placa);
    Task<List<string>> BuscarPlacasAsync(string q);
    Task<List<ChoferDto>> ListarChoferesPorTransportistaAsync(string idTransportista);
    Task<List<ProductoDto>> ListarProductosAsync();
    Task<List<ProductoDto>> BuscarProductosRealesAsync(string q);
    Task<List<SuplidorDto>> BuscarSuplidoresAsync(string query);
    Task<object> ObtenerConfiguracionAsync();
    Task<byte[]?> ObtenerLogoAsync();
    Task<List<AlmacenDto>> ListarAlmacenesAsync(string? usuario = null);
    Task<Guid> RegistrarEntradaAsync(RegistrarEntradaRequest req, string usuario);
    Task<bool> CancelarEntradaAsync(Guid idEntradaCamion, string usuario);
    Task<bool> ConfirmarRecepcionAsync(Guid idEntradaCamion, DateTime fechaRecepcion, string usuarioRecepcion, Guid idEvidencia, ConfirmarRecepcionRequest req);
    Task<bool> AsignarOrdenAsync(AsignarOcRequest req, string usuario);
    Task<List<EntradaCamionDto>> ConsultarRecepcionesAsync(ConsultaFiltros filtros);
    Task<List<EntradaCamionDto>> ObtenerPendientesCierreAsync(DateOnly fechaDia);
    Task<CierreDiaResultDto> EjecutarCierreDiaAsync(DateOnly fechaDia, string usuario, string? notas);
    Task<EntradaCamionDto?> ObtenerEntradaPorIdAsync(Guid idEntradaCamion);
    Task<List<EntradaCamionDto>> ObtenerEntradasHoyAsync(string? idPuerta, string? usuarioPermiso = null);
}

public class PuertaDbService : IPuertaDbService
{
    private readonly IConnectionFactory _cf;
    private readonly ILogger<PuertaDbService> _logger;

    public PuertaDbService(IConnectionFactory cf, ILogger<PuertaDbService> logger)
    {
        _cf     = cf;
        _logger = logger;
    }

    // ── Buscar transportista por placa ────────────────────────────────────────
    public async Task<TransportistaDto?> BuscarTransportistaPorPlacaAsync(string placa)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText  = "prtBuscarTransportistaPorPlaca";
        cmd.CommandType  = System.Data.CommandType.StoredProcedure;
        cmd.Parameters.AddWithValue("@Placa", placa.Trim().ToUpper());

        await using var reader = await cmd.ExecuteReaderAsync();
        if (!await reader.ReadAsync()) return null;

        var dto = new TransportistaDto
        {
            IdTransportista = reader["idTransportista"].ToString()!,
            Nombre          = reader["Transportista"].ToString()!,
            Telefono        = reader["Telefono"] as string,
            Status          = reader["Status"].ToString()!,
            IdEquipo        = Guid.Parse(reader["idTransportistaEquipo"].ToString()!),
            PlacaNo         = reader["PlacaNo"].ToString()!,
            PlacaVence      = reader["PlacaVence"] as DateTime?,
            NombreEquipo    = reader["TransportistaEquipo"] as string,
            Capacidad       = reader["Capacidad"] as decimal?,
            IdUnidad        = reader["idUnidad"] as string
        };

        reader.Close();

        // Cargar choferes
        dto = dto with { Choferes = await ListarChoferesPorTransportistaAsync(dto.IdTransportista) };
        return dto;
    }

    // ── Buscar placas ────────────────────────────────────────────────────────
    public async Task<List<string>> BuscarPlacasAsync(string q)
    {
        var lista = new List<string>();
        if (string.IsNullOrWhiteSpace(q) || q.Length < 2) return lista;

        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            SELECT TOP 20 e.PlacaNo 
            FROM lgTransportistaEquipo e
            INNER JOIN lgTransportista t ON e.idTransportista = t.idTransportista
            WHERE e.PlacaNo LIKE '%' + @q + '%' AND t.Status = 'ACTIVO'
        ";
        cmd.CommandType = System.Data.CommandType.Text;
        cmd.Parameters.AddWithValue("@q", q.Trim());

        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            lista.Add(reader["PlacaNo"].ToString()!);
        }

        return lista;
    }

    // ── Listar choferes ───────────────────────────────────────────────────────
    public async Task<List<ChoferDto>> ListarChoferesPorTransportistaAsync(string idTransportista)
    {
        var lista = new List<ChoferDto>();
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText  = "prtListarChoferesPorTransportista";
        cmd.CommandType  = System.Data.CommandType.StoredProcedure;
        cmd.Parameters.AddWithValue("@idTransportista", idTransportista);

        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            lista.Add(new ChoferDto
            {
                IdChofer    = Guid.Parse(reader["idTransportistaChofer"].ToString()!),
                Nombre      = reader["NombreChofer"].ToString()!,
                LicenciaNo  = reader["LicenciaNo"] as string,
                Celular     = reader["Celular"] as string
            });
        }
        return lista;
    }

    // ── Listar Productos (Simulada por ahora) ─────────────────────────────────
    public async Task<List<ProductoDto>> ListarProductosAsync()
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT idProductoPuerta, idProducto, Producto FROM invProductoPuerta ORDER BY Producto";

        var lista = new List<ProductoDto>();
        await using var r = await cmd.ExecuteReaderAsync();
        while (await r.ReadAsync())
        {
            lista.Add(new ProductoDto
            {
                IdProductoPuerta = r["idProductoPuerta"].ToString()!,
                IdProducto = r["idProducto"].ToString()!,
                Nombre = r["Producto"].ToString()!
            });
        }
        return lista;
    }

    // ── Buscar Productos Reales en ERP (Materia Prima) ──────────────────
    public async Task<List<ProductoDto>> BuscarProductosRealesAsync(string q)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            SELECT TOP 50 p.idProducto, p.Producto 
            FROM Producto p
            WHERE p.Producto LIKE '%' + @q + '%' OR p.idProducto LIKE '%' + @q + '%'
            ORDER BY p.Producto";
        
        cmd.Parameters.AddWithValue("@q", q);

        var lista = new List<ProductoDto>();
        await using var r = await cmd.ExecuteReaderAsync();
        while (await r.ReadAsync())
        {
            lista.Add(new ProductoDto
            {
                IdProductoPuerta = r["idProducto"].ToString()!, // Reuse this property for the real ID for convenience, or better just use IdProducto
                IdProducto = r["idProducto"].ToString()!,
                Nombre = r["Producto"].ToString()!
            });
        }
        return lista;
    }

    // ── Buscar Suplidores ─────────────────────────────────────────────────────
    public async Task<List<SuplidorDto>> BuscarSuplidoresAsync(string q)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            SELECT TOP 50 idSuplidor, Nombre 
            FROM cxpSuplidores 
            WHERE Estatus = 1 AND Nombre LIKE @q
            ORDER BY Nombre";
            
        cmd.Parameters.AddWithValue("@q", "%" + q + "%");

        var lista = new List<SuplidorDto>();
        await using var r = await cmd.ExecuteReaderAsync();
        while (await r.ReadAsync())
        {
            lista.Add(new SuplidorDto
            {
                IdSuplidor = r["idSuplidor"].ToString()!,
                Nombre = r["Nombre"].ToString()!
            });
        }
        return lista;
    }

    // ── Listar Almacenes ──────────────────────────────────────────────────────
    public async Task<List<AlmacenDto>> ListarAlmacenesAsync(string? usuario = null)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        // Si hay usuario, filtrar solo almacenes a los que tiene permiso
        cmd.CommandText = @"
            SELECT a.idAlmacen, a.Almacen 
            FROM Almacen a
            WHERE @usuario IS NULL 
               OR a.idAlmacen IN (SELECT idAlmacen FROM AlmacenPermiso WHERE idSegUserGrp = @usuario)
            ORDER BY a.Almacen";
        cmd.Parameters.AddWithValue("@usuario", (object?)usuario ?? DBNull.Value);

        var lista = new List<AlmacenDto>();
        await using var r = await cmd.ExecuteReaderAsync();
        while (await r.ReadAsync())
        {
            lista.Add(new AlmacenDto
            {
                IdAlmacen = r["idAlmacen"].ToString()!,
                Nombre = r["Almacen"].ToString()!
            });
        }
        return lista;
    }

    // ── Registrar Entrada en Puerta ───────────────────────────────────────────
    public async Task<Guid> RegistrarEntradaAsync(RegistrarEntradaRequest req, string usuario)
    {
        var idEntrada = Guid.NewGuid();

        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();
        await using var tran = conn.BeginTransaction();

        try
        {
            // Insertar entrada principal
            await using var cmd = conn.CreateCommand();
            cmd.Transaction  = tran;
            cmd.CommandText  = "prtRegistrarEntrada";
            cmd.CommandType  = System.Data.CommandType.StoredProcedure;

            cmd.Parameters.AddWithValue("@idEntradaCamion",  idEntrada);
            cmd.Parameters.AddWithValue("@Conduce",          req.Conduce);
            cmd.Parameters.AddWithValue("@Placa",            req.Placa.ToUpper().Trim());
            cmd.Parameters.AddWithValue("@PlacaOcrTexto",    (object?)req.PlacaOcrTexto     ?? DBNull.Value);
            cmd.Parameters.AddWithValue("@PlacaOcrConfianza",(object?)req.PlacaOcrConfianza ?? DBNull.Value);
            cmd.Parameters.AddWithValue("@idTransportista",  (object?)req.IdTransportista   ?? DBNull.Value);
            cmd.Parameters.AddWithValue("@Transportista",    (object?)req.Transportista      ?? DBNull.Value);
            cmd.Parameters.AddWithValue("@idChofer",         (object?)req.IdChofer           ?? DBNull.Value);
            cmd.Parameters.AddWithValue("@NombreChofer",     (object?)req.NombreChofer       ?? DBNull.Value);
            cmd.Parameters.AddWithValue("@idProducto",       (object?)req.IdProducto         ?? DBNull.Value);
            cmd.Parameters.AddWithValue("@Producto",         (object?)req.Producto           ?? DBNull.Value);
            cmd.Parameters.AddWithValue("@idAlmacen",        (object?)req.IdAlmacen          ?? DBNull.Value);
            cmd.Parameters.AddWithValue("@idPuerta",         (object?)req.IdPuerta           ?? DBNull.Value);
            cmd.Parameters.AddWithValue("@Notas",            (object?)req.Notas              ?? DBNull.Value);
            cmd.Parameters.AddWithValue("@Usuario",          usuario);
            cmd.Parameters.AddWithValue("@CantidadDeclarada", (object?)req.CantidadDeclarada ?? DBNull.Value);

            await using var reader = await cmd.ExecuteReaderAsync();
            if (await reader.ReadAsync())
            {
                var resultado = reader["Resultado"].ToString();
                if (resultado == "ERROR")
                {
                    var mensaje = reader["Mensaje"].ToString();
                    throw new Exception(mensaje); // It will be caught by global handler or we can return custom. 
                }
            }
            await reader.CloseAsync();
            // Insertar detalle de productos si hay
            if (req.Productos.Any())
            {
                foreach (var (prod, i) in req.Productos.Select((p, i) => (p, i + 1)))
                {
                    await using var cmdDet = conn.CreateCommand();
                    cmdDet.Transaction  = tran;
                    cmdDet.CommandText  = @"INSERT INTO prtEntradaDetalle
                        (idEntradaDetalle, idEntradaCamion, idProducto, Producto, Cantidad, idUnidad, Notas, Orden)
                        VALUES (NEWID(), @id, @idProd, @prod, @cant, @uni, @notas, @orden)";

                    cmdDet.Parameters.AddWithValue("@id",     idEntrada);
                    cmdDet.Parameters.AddWithValue("@idProd", (object?)prod.IdProducto ?? DBNull.Value);
                    cmdDet.Parameters.AddWithValue("@prod",   (object?)prod.Producto   ?? DBNull.Value);
                    cmdDet.Parameters.AddWithValue("@cant",   (object?)prod.Cantidad   ?? DBNull.Value);
                    cmdDet.Parameters.AddWithValue("@uni",    (object?)prod.IdUnidad   ?? DBNull.Value);
                    cmdDet.Parameters.AddWithValue("@notas",  (object?)prod.Notas      ?? DBNull.Value);
                    cmdDet.Parameters.AddWithValue("@orden",  i);

                    await cmdDet.ExecuteNonQueryAsync();
                }
            }

            await tran.CommitAsync();
            _logger.LogInformation("[PUERTA] Entrada registrada: {Id} | Conduce: {Cond} | Placa: {Placa}", idEntrada, req.Conduce, req.Placa);
            return idEntrada;
        }
        catch
        {
            await tran.RollbackAsync();
            throw;
        }
    }

    // ── Confirmar Recepción (y generar movimiento de inventario) ──────────────
    public async Task<bool> ConfirmarRecepcionAsync(Guid idEntradaCamion, DateTime fechaRecepcion, string usuarioRecepcion, Guid idEvidencia, ConfirmarRecepcionRequest req)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        // Validar duplicados de Conduce Agregado + Suplidor
        if (!string.IsNullOrWhiteSpace(req.Conduce) && !string.IsNullOrWhiteSpace(req.IdSuplidor))
        {
            await using var cmdDup = conn.CreateCommand();
            cmdDup.CommandText = "SELECT COUNT(1) FROM prtEntradaCamion WHERE Conduce = @c AND idSuplidor = @s AND idEntradaCamion != @id";
            cmdDup.Parameters.AddWithValue("@c", req.Conduce);
            cmdDup.Parameters.AddWithValue("@s", req.IdSuplidor);
            cmdDup.Parameters.AddWithValue("@id", idEntradaCamion);
            var exists = (int)(await cmdDup.ExecuteScalarAsync() ?? 0) > 0;
            if (exists)
                throw new InvalidOperationException($"El Conduce '{req.Conduce}' ya se encuentra registrado para este suplidor.");
        }

        // 1. Actualizar entrada
        await using var cmd = conn.CreateCommand();
        
        // If the warehouse worker selected a real product, we update idProducto and Producto in prtEntradaCamion
        // so that prtGenerarMovimientoEntrada and prtEjecutarCierreDia will use it.
        string updateProductSql = "";
        if (!string.IsNullOrWhiteSpace(req.IdProductoReal))
        {
            updateProductSql = ", idProducto = @idProductoReal"; // Solo el ID, para no alterar el texto visible en el módulo de puerta
        }

        cmd.CommandText = $@"
            UPDATE prtEntradaCamion 
            SET Status = 'RECIBIDO', 
                Conduce = @Conduce,
                ConduceTransporte = @ConduceTransporte,
                FechaRecepcion = @FechaRecepcion,
                UsuarioRecepcion = @UsuarioRecepcion,
                CantidadRecibida = @CantidadRecibida,
                idSuplidor = @idSuplidor,
                Suplidor = @Suplidor,
                idAlmacen = @idAlmacen,
                Notas = ISNULL(Notas, '') + ' ' + ISNULL(@Notas, '')
                {updateProductSql}
            WHERE idEntradaCamion = @idEntradaCamion AND Status = 'PENDIENTE'
        ";
        cmd.Parameters.AddWithValue("@idEntradaCamion", idEntradaCamion);
        cmd.Parameters.AddWithValue("@Conduce", req.Conduce);
        cmd.Parameters.AddWithValue("@ConduceTransporte", req.ConduceTransporte);
        cmd.Parameters.AddWithValue("@FechaRecepcion", fechaRecepcion);
        cmd.Parameters.AddWithValue("@UsuarioRecepcion", usuarioRecepcion);
        cmd.Parameters.AddWithValue("@CantidadRecibida", req.CantidadRecibida);
        cmd.Parameters.AddWithValue("@idSuplidor", (object?)req.IdSuplidor ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@Suplidor", (object?)req.NombreSuplidor ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@idAlmacen", (object?)req.IdAlmacen ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@Notas", (object?)req.Notas ?? DBNull.Value);

        if (!string.IsNullOrWhiteSpace(req.IdProductoReal))
        {
            cmd.Parameters.AddWithValue("@idProductoReal", req.IdProductoReal);
            cmd.Parameters.AddWithValue("@NombreProductoReal", req.NombreProductoReal);
        }

        var rows = await cmd.ExecuteNonQueryAsync();
        if (rows == 0) return false;

        // 2. Insertar Evidencia
        await using var cmdEv = conn.CreateCommand();
        cmdEv.CommandText = @"
            INSERT INTO prtEntradaEvidencia (idEntradaCamion, idEvidencia)
            VALUES (@id, @idEv)
        ";
        cmdEv.Parameters.AddWithValue("@id", idEntradaCamion);
        cmdEv.Parameters.AddWithValue("@idEv", idEvidencia);
        await cmdEv.ExecuteNonQueryAsync();

        // 3. Generar movimiento de almacén
        await using var cmdSp = conn.CreateCommand();
        cmdSp.CommandText = "prtGenerarMovimientoEntrada";
        cmdSp.CommandType = System.Data.CommandType.StoredProcedure;
        cmdSp.Parameters.AddWithValue("@idEntradaCamion", idEntradaCamion);
        cmdSp.Parameters.AddWithValue("@Usuario", usuarioRecepcion);
        await cmdSp.ExecuteNonQueryAsync();

        return true;
    }

    // ── Asignar OC a una entrada ──────────────────────────────────────────────
    public async Task<bool> AsignarOrdenAsync(AsignarOcRequest req, string usuario)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = @"UPDATE prtEntradaCamion SET
            idOrden = @idOrden, OrdenNumero = @num,
            EvalCalidad = @calidad, EvalTiempo = @tiempo, EvalServicio = @servicio,
            FechaModificacion = GETDATE(), UsuarioModificacion = @usr
            WHERE idEntradaCamion = @id";

        cmd.Parameters.AddWithValue("@idOrden", req.IdOrden);
        cmd.Parameters.AddWithValue("@num",     req.OrdenNumero);
        cmd.Parameters.AddWithValue("@calidad", req.EvalCalidad);
        cmd.Parameters.AddWithValue("@tiempo",  req.EvalTiempo);
        cmd.Parameters.AddWithValue("@servicio",req.EvalServicio);
        cmd.Parameters.AddWithValue("@usr",     usuario);
        cmd.Parameters.AddWithValue("@id",      req.IdEntradaCamion);

        return await cmd.ExecuteNonQueryAsync() > 0;
    }

    // ── Consultar recepciones con filtros ─────────────────────────────────────
    public async Task<List<EntradaCamionDto>> ConsultarRecepcionesAsync(ConsultaFiltros filtros)
    {
        var lista = new List<EntradaCamionDto>();
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText  = "prtConsultarRecepciones";
        cmd.CommandType  = System.Data.CommandType.StoredProcedure;
        cmd.Parameters.AddWithValue("@FechaDesde",    (object?)filtros.FechaDesde?.ToDateTime(TimeOnly.MinValue)    ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@FechaHasta",    (object?)filtros.FechaHasta?.ToDateTime(TimeOnly.MaxValue)    ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@Conduce",       (object?)filtros.Conduce        ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@Placa",         (object?)filtros.Placa          ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@Transportista", (object?)filtros.Transportista  ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@Status",        (object?)filtros.Status         ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@PageNumber",    filtros.PageNumber);
        cmd.Parameters.AddWithValue("@PageSize",      filtros.PageSize);
        cmd.Parameters.AddWithValue("@UsuarioPermiso",(object?)filtros.UsuarioPermiso ?? DBNull.Value);

        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
            lista.Add(MapearEntrada(reader));

        return lista;
    }

    // ── Recepciones pendientes de cierre ──────────────────────────────────────
    public async Task<List<EntradaCamionDto>> ObtenerPendientesCierreAsync(DateOnly fechaDia)
    {
        var lista = new List<EntradaCamionDto>();
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText  = "prtObtenerPendientesCierre";
        cmd.CommandType  = System.Data.CommandType.StoredProcedure;
        cmd.Parameters.AddWithValue("@FechaDia", fechaDia.ToDateTime(TimeOnly.MinValue));

        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
            lista.Add(MapearEntrada(reader));

        return lista;
    }

    // ── Ejecutar cierre del día ───────────────────────────────────────────────
    public async Task<CierreDiaResultDto> EjecutarCierreDiaAsync(DateOnly fechaDia, string usuario, string? notas)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText  = "prtEjecutarCierreDia";
        cmd.CommandType  = System.Data.CommandType.StoredProcedure;
        cmd.CommandTimeout = 120;
        cmd.Parameters.AddWithValue("@FechaDia",      fechaDia.ToDateTime(TimeOnly.MinValue));
        cmd.Parameters.AddWithValue("@UsuarioCierre", usuario);
        cmd.Parameters.AddWithValue("@Notas",         (object?)notas ?? DBNull.Value);

        await using var reader = await cmd.ExecuteReaderAsync();
        await reader.ReadAsync();

        return new CierreDiaResultDto
        {
            IdCierre         = Guid.Parse(reader["idCierre"].ToString()!),
            FechaDia         = fechaDia,
            TotalRecepciones = (int)reader["TotalRecepciones"],
            TotalConOC       = (int)reader["TotalConOC"],
            TotalSinOC       = (int)reader["TotalSinOC"]
        };
    }

    // ── Cancelar entrada en puerta ───────────────────────────────────────────
    public async Task<bool> CancelarEntradaAsync(Guid idEntradaCamion, string usuario)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            UPDATE prtEntradaCamion 
            SET Status = 'CANCELADO',
                Notas = ISNULL(Notas, '') + ' [Cancelado por ' + @Usuario + ' el ' + CONVERT(varchar, GETDATE(), 120) + ']'
            WHERE idEntradaCamion = @idEntradaCamion AND Status = 'PENDIENTE'
        ";
        cmd.Parameters.AddWithValue("@idEntradaCamion", idEntradaCamion);
        cmd.Parameters.AddWithValue("@Usuario", usuario);

        var rows = await cmd.ExecuteNonQueryAsync();
        return rows > 0;
    }

    // ── Obtener entrada por ID ────────────────────────────────────────────────
    public async Task<EntradaCamionDto?> ObtenerEntradaPorIdAsync(Guid idEntradaCamion)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = @"SELECT e.*, 0 AS TotalRegistros
            FROM prtEntradaCamion e WHERE e.idEntradaCamion = @id";
        cmd.Parameters.AddWithValue("@id", idEntradaCamion);

        await using var reader = await cmd.ExecuteReaderAsync();
        return await reader.ReadAsync() ? MapearEntrada(reader) : null;
    }

    // ── Entradas de hoy para monitor ─────────────────────────────────────────
    public async Task<List<EntradaCamionDto>> ObtenerEntradasHoyAsync(string? idPuerta, string? usuarioPermiso = null)
    {
        var lista = new List<EntradaCamionDto>();
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            SELECT e.*, 0 AS TotalRegistros
            FROM prtEntradaCamion e
            WHERE CAST(e.FechaEntrada AS DATE) = CAST(GETDATE() AS DATE)
              AND (@idPuerta IS NULL OR e.idPuerta = @idPuerta)
              AND (@usuarioPermiso IS NULL OR e.idAlmacen IS NULL OR e.idAlmacen IN (SELECT idAlmacen FROM AlmacenPermiso WHERE idSegUserGrp = @usuarioPermiso))
            ORDER BY e.FechaEntrada DESC";
        cmd.Parameters.AddWithValue("@idPuerta", (object?)idPuerta ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@usuarioPermiso", (object?)usuarioPermiso ?? DBNull.Value);

        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
            lista.Add(MapearEntrada(reader));

        return lista;
    }

    // ── Mapper ────────────────────────────────────────────────────────────────
    private static EntradaCamionDto MapearEntrada(SqlDataReader r)
    {
        static T? Get<T>(SqlDataReader r, string col) where T : struct
            => r.IsDBNull(r.GetOrdinal(col)) ? null : r.GetFieldValue<T>(r.GetOrdinal(col));
        static string? GetStr(SqlDataReader r, string col)
            => r.IsDBNull(r.GetOrdinal(col)) ? null : r.GetString(r.GetOrdinal(col));

        return new EntradaCamionDto
        {
            IdEntradaCamion  = r.GetGuid(r.GetOrdinal("idEntradaCamion")),
            Conduce          = r.GetString(r.GetOrdinal("Conduce")),
            Placa            = r.GetString(r.GetOrdinal("Placa")),
            IdTransportista  = GetStr(r, "idTransportista"),
            Transportista    = GetStr(r, "Transportista"),
            IdChofer         = Get<Guid>(r, "idChofer"),
            NombreChofer     = GetStr(r, "NombreChofer"),
            FechaEntrada     = r.GetDateTime(r.GetOrdinal("FechaEntrada")),
            FechaRecepcion   = Get<DateTime>(r, "FechaRecepcion"),
            UsuarioRecepcion = GetStr(r, "UsuarioRecepcion"),
            IdProducto       = GetStr(r, "idProducto"),
            Producto         = GetStr(r, "Producto"),
            IdSuplidor       = GetStr(r, "idSuplidor"),
            Suplidor         = GetStr(r, "Suplidor"),
            CantidadRecibida = Get<decimal>(r, "CantidadRecibida"),
            IdAlmacen        = GetStr(r, "idAlmacen"),
            Status           = r.GetString(r.GetOrdinal("Status")),
            IdOrden          = Get<Guid>(r, "idOrden"),
            OrdenNumero      = Get<int>(r, "OrdenNumero"),
            IdEvidencia      = Get<Guid>(r, "idEvidencia"),
            Notas            = GetStr(r, "Notas"),
            Usuario          = GetStr(r, "Usuario") ?? "",
            IdPuerta         = GetStr(r, "idPuerta"),
            ProMov           = GetStr(r, "ProMov"),
            NumRecepcionOC   = HasColumn(r, "NumRecepcionOC") ? GetStr(r, "NumRecepcionOC") : null,
            TotalRegistros   = HasColumn(r, "TotalRegistros") ? r.GetInt32(r.GetOrdinal("TotalRegistros")) : 0
        };
    }

    private static bool HasColumn(SqlDataReader reader, string columnName)
    {
        for (int i = 0; i < reader.FieldCount; i++)
        {
            if (reader.GetName(i).Equals(columnName, StringComparison.OrdinalIgnoreCase))
                return true;
        }
        return false;
    }

    public async Task<object> ObtenerConfiguracionAsync()
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();
        var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT TOP 1 companiacorto FROM Configuracion";
        using var reader = await cmd.ExecuteReaderAsync();
        if (await reader.ReadAsync())
        {
            return new { CompaniaCorto = reader["companiacorto"]?.ToString() };
        }
        return new { CompaniaCorto = "SADE" };
    }

    public async Task<byte[]?> ObtenerLogoAsync()
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();
        var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT TOP 1 logo FROM Configuracion";
        using var reader = await cmd.ExecuteReaderAsync();
        if (await reader.ReadAsync())
        {
            if (reader["logo"] != DBNull.Value)
            {
                return (byte[])reader["logo"];
            }
        }
        return null;
    }
}
