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
    Task<string?> ConfirmarRecepcionAsync(Guid idEntradaCamion, DateTime fechaRecepcion, string usuarioRecepcion, Guid? idEvidencia, ConfirmarRecepcionRequest req);
    Task AsignarEvidenciaAsync(Guid idEntradaCamion, Guid idEvidencia);
    Task<List<ChoferDto>> BuscarChoferesAsync(string q);
    Task<List<TicketProductoDto>> ObtenerProductosTicketAsync(Guid idEntradaCamion, string? conduceTransporte, string conduce, string? placa, DateTime fechaEntrada);
    Task<List<string>> ListarUnidadesAsync();
    Task<(string? identificador, string? revision)> ObtenerParametrosIsoAsync();
    Task<string?> ObtenerNombreEmpresaAsync();
    Task<bool> AsignarOrdenAsync(AsignarOcRequest req, string usuario);
    Task<List<EntradaCamionDto>> ConsultarRecepcionesAsync(ConsultaFiltros filtros);
    Task<List<EntradaCamionDto>> ObtenerPendientesCierreAsync(DateOnly fechaDia);
    Task<CierreDiaResultDto> EjecutarCierreDiaAsync(DateOnly fechaDia, string usuario, string? notas);
    Task<EntradaCamionDto?> ObtenerEntradaPorIdAsync(Guid idEntradaCamion);
    Task<List<EntradaCamionDto>> ObtenerEntradasHoyAsync(string? idPuerta, string? usuarioPermiso = null);
    Task<ResultadoConciliacionDto> CompararConducesAsync(CompararConciliacionRequest req, string usuario);
    Task<Guid> GuardarLoteConciliacionAsync(GuardarConciliacionRequest req, string usuario);
    Task<List<LoteConciliacionDto>> ListarLotesConciliacionAsync(string? idSuplidor, string? status);
    Task<ResultadoConciliacionDto?> ObtenerLoteConciliacionAsync(Guid idConciliacion);
    Task<bool> ActualizarEstadoPagoLoteAsync(Guid idConciliacion, ActualizarEstadoPagoRequest req, string usuario);
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
            WHERE e.PlacaNo LIKE '%' + @q + '%' AND t.Status = 'ACTIVO' AND e.Status = 'ACTIVO' AND UPPER(LTRIM(RTRIM(e.PlacaNo))) NOT IN ('GENERICA', 'S/P', 'SIN PLACA') AND t.idTransportista <> 'GENERICO' AND t.Transportista NOT LIKE '%GENERIC%'
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
            SELECT TOP 50 p.idProducto, p.Producto, p.idUnidad 
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
    public async Task<string?> ConfirmarRecepcionAsync(Guid idEntradaCamion, DateTime fechaRecepcion, string usuarioRecepcion, Guid? idEvidencia, ConfirmarRecepcionRequest req)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        if (!string.IsNullOrWhiteSpace(req.Conduce) && !string.IsNullOrWhiteSpace(req.IdSuplidor))
        {
            await using var cmdDup = conn.CreateCommand();
            cmdDup.CommandText = "SELECT COUNT(1) FROM prtEntradaCamion WHERE Conduce = @c AND idSuplidor = @s AND idEntradaCamion != @id";
            cmdDup.Parameters.AddWithValue("@c", req.Conduce);
            cmdDup.Parameters.AddWithValue("@s", req.IdSuplidor);
            cmdDup.Parameters.AddWithValue("@id", idEntradaCamion);
            var exists = (int)(await cmdDup.ExecuteScalarAsync() ?? 0) > 0;
            if (exists) throw new InvalidOperationException($"El Conduce '{req.Conduce}' ya se encuentra registrado para este suplidor.");
        }

        string almacenKey = string.IsNullOrWhiteSpace(req.IdAlmacen) ? "GENERAL" : req.IdAlmacen.Trim();
        string secuenciaGenerada;
        await using (var cmdSeq = conn.CreateCommand())
        {
            cmdSeq.CommandText = "prtObtenerSiguienteSecuenciaAlmacen";
            cmdSeq.CommandType = System.Data.CommandType.StoredProcedure;
            cmdSeq.Parameters.AddWithValue("@idAlmacen", almacenKey);
            var pOut = cmdSeq.Parameters.Add("@SecuenciaGenerada", System.Data.SqlDbType.VarChar, 50);
            pOut.Direction = System.Data.ParameterDirection.Output;
            await cmdSeq.ExecuteNonQueryAsync();
            secuenciaGenerada = pOut.Value?.ToString() ?? $"{almacenKey}-00001";
        }

        var productos = req.Productos ?? new System.Collections.Generic.List<ProductoRecepcionDto>();
        if (productos.Count == 0) throw new InvalidOperationException("Debe agregar al menos un producto.");

        var entradasGeneradas = new System.Collections.Generic.List<Guid>();
        using var tran = conn.BeginTransaction();
        try
        {
            for (int i = 0; i < productos.Count; i++)
            {
                var p = productos[i];
                var isPrimary = (i == 0);
                var currentIdEntrada = isPrimary ? idEntradaCamion : Guid.NewGuid();
                entradasGeneradas.Add(currentIdEntrada);

                if (!isPrimary)
                {
                    await using var cmdDup2 = conn.CreateCommand();
                    cmdDup2.Transaction = tran;
                    cmdDup2.CommandText = @"
                        INSERT INTO prtEntradaCamion (
                            idEntradaCamion, Conduce, FechaEntrada, idTransportista, Transportista, Placa,
                            idChofer, NombreChofer, FechaRecepcion, UsuarioRecepcion, idAlmacen, idPuerta,
                            Status, Usuario, FechaCreacion, ConduceTransporte, idSuplidor, Suplidor,
                            idEvidencia, Notas, idProducto, Producto, CantidadRecibida, idUnidad, idUnidadAlmacen, CantidadAlmacen
                        )
                        SELECT 
                            @newId, @cond, FechaEntrada, idTransportista, Transportista, Placa,
                            idChofer, NombreChofer, @fechaRec, @usuRec, @idAlm, idPuerta,
                            'RECIBIDO', Usuario, FechaCreacion, @condTrans, @idSup, @nomSup,
                            @idEv, @notas, @idProd, @nomProd, @cant, @idUni, @idUniAlm, @cantAlm
                        FROM prtEntradaCamion WHERE idEntradaCamion = @origId";
                    cmdDup2.Parameters.AddWithValue("@origId", idEntradaCamion);
                    cmdDup2.Parameters.AddWithValue("@newId", currentIdEntrada);
                    cmdDup2.Parameters.AddWithValue("@cond", req.Conduce);
                    cmdDup2.Parameters.AddWithValue("@fechaRec", fechaRecepcion);
                    cmdDup2.Parameters.AddWithValue("@usuRec", usuarioRecepcion);
                    cmdDup2.Parameters.AddWithValue("@idAlm", (object?)req.IdAlmacen ?? DBNull.Value);
                    cmdDup2.Parameters.AddWithValue("@condTrans", secuenciaGenerada);
                    cmdDup2.Parameters.AddWithValue("@idSup", (object?)req.IdSuplidor ?? DBNull.Value);
                    cmdDup2.Parameters.AddWithValue("@nomSup", (object?)req.NombreSuplidor ?? DBNull.Value);
                    cmdDup2.Parameters.AddWithValue("@idEv", (object?)idEvidencia ?? DBNull.Value);
                    cmdDup2.Parameters.AddWithValue("@notas", (object?)req.Notas ?? DBNull.Value);
                    cmdDup2.Parameters.AddWithValue("@idProd", (object?)p.IdProductoReal ?? DBNull.Value);
                    cmdDup2.Parameters.AddWithValue("@nomProd", (object?)p.NombreProductoReal ?? DBNull.Value);
                    cmdDup2.Parameters.AddWithValue("@cant", p.CantidadRecibida);
                    cmdDup2.Parameters.AddWithValue("@idUni", (object?)p.IdUnidad ?? DBNull.Value);
                    cmdDup2.Parameters.AddWithValue("@idUniAlm", (object?)p.IdUnidadAlmacen ?? DBNull.Value);
                    cmdDup2.Parameters.AddWithValue("@cantAlm", (object?)p.CantidadAlmacen ?? DBNull.Value);
                    await cmdDup2.ExecuteNonQueryAsync();
                }
                else
                {
                    await using var cmdU = conn.CreateCommand();
                    cmdU.Transaction = tran;
                    string updateProductSql = ", idProducto = @idProductoReal, Producto = ISNULL(@NombreProductoReal, Producto)";
                    cmdU.CommandText = $"UPDATE prtEntradaCamion SET Status = 'RECIBIDO', Conduce = @Conduce, ConduceTransporte = @ConduceTransporte, FechaRecepcion = @FechaRecepcion, UsuarioRecepcion = @UsuarioRecepcion, CantidadRecibida = @CantidadRecibida, idSuplidor = @idSuplidor, Suplidor = @Suplidor, idAlmacen = @idAlmacen, idEvidencia = @idEvidencia, idUnidad = @idUnidad, idUnidadAlmacen = @idUnidadAlmacen, CantidadAlmacen = @CantidadAlmacen, Notas = ISNULL(Notas, '') + ' ' + ISNULL(@Notas, '') {updateProductSql} WHERE idEntradaCamion = @idEntradaCamion";
                    cmdU.Parameters.AddWithValue("@idEntradaCamion", idEntradaCamion);
                    cmdU.Parameters.AddWithValue("@Conduce", req.Conduce);
                    cmdU.Parameters.AddWithValue("@ConduceTransporte", secuenciaGenerada);
                    cmdU.Parameters.AddWithValue("@FechaRecepcion", fechaRecepcion);
                    cmdU.Parameters.AddWithValue("@UsuarioRecepcion", usuarioRecepcion);
                    cmdU.Parameters.AddWithValue("@CantidadRecibida", p.CantidadRecibida);
                    cmdU.Parameters.AddWithValue("@idSuplidor", (object?)req.IdSuplidor ?? DBNull.Value);
                    cmdU.Parameters.AddWithValue("@Suplidor", (object?)req.NombreSuplidor ?? DBNull.Value);
                    cmdU.Parameters.AddWithValue("@idAlmacen", (object?)req.IdAlmacen ?? DBNull.Value);
                    cmdU.Parameters.AddWithValue("@idEvidencia", (object?)idEvidencia ?? DBNull.Value);
                    cmdU.Parameters.AddWithValue("@idUnidad", (object?)p.IdUnidad ?? DBNull.Value);
                    cmdU.Parameters.AddWithValue("@idUnidadAlmacen", (object?)p.IdUnidadAlmacen ?? DBNull.Value);
                    cmdU.Parameters.AddWithValue("@CantidadAlmacen", (object?)p.CantidadAlmacen ?? DBNull.Value);
                    cmdU.Parameters.AddWithValue("@Notas", (object?)req.Notas ?? DBNull.Value);
                    cmdU.Parameters.AddWithValue("@idProductoReal", (object?)p.IdProductoReal ?? DBNull.Value);
                    cmdU.Parameters.AddWithValue("@NombreProductoReal", (object?)p.NombreProductoReal ?? DBNull.Value);
                    await cmdU.ExecuteNonQueryAsync();
                }

                if (isPrimary)
                {
                    await using var cmdDet1 = conn.CreateCommand();
                    cmdDet1.Transaction = tran;
                    cmdDet1.CommandText = "UPDATE prtEntradaDetalle SET idProducto = ISNULL(@idProd, idProducto), Producto = ISNULL(@prod, Producto), Cantidad = @cant, idUnidad = ISNULL(@idUnidad, idUnidad) WHERE idEntradaCamion = @id";
                    cmdDet1.Parameters.AddWithValue("@id", idEntradaCamion);
                    cmdDet1.Parameters.AddWithValue("@idProd", (object?)p.IdProductoReal ?? DBNull.Value);
                    cmdDet1.Parameters.AddWithValue("@prod", (object?)p.NombreProductoReal ?? DBNull.Value);
                    cmdDet1.Parameters.AddWithValue("@cant", p.CantidadRecibida);
                    cmdDet1.Parameters.AddWithValue("@idUnidad", (object?)p.IdUnidad ?? DBNull.Value);
                    await cmdDet1.ExecuteNonQueryAsync();
                }
                else
                {
                    await using var cmdDet2 = conn.CreateCommand();
                    cmdDet2.Transaction = tran;
                    cmdDet2.CommandText = "INSERT INTO prtEntradaDetalle (idEntradaDetalle, idEntradaCamion, idProducto, Producto, Cantidad, idUnidad, Orden) VALUES (NEWID(), @id, @idProd, @prod, @cant, @idUnidad, 1)";
                    cmdDet2.Parameters.AddWithValue("@id", currentIdEntrada);
                    cmdDet2.Parameters.AddWithValue("@idProd", (object?)p.IdProductoReal ?? DBNull.Value);
                    cmdDet2.Parameters.AddWithValue("@prod", (object?)p.NombreProductoReal ?? DBNull.Value);
                    cmdDet2.Parameters.AddWithValue("@cant", p.CantidadRecibida);
                    cmdDet2.Parameters.AddWithValue("@idUnidad", (object?)p.IdUnidad ?? DBNull.Value);
                    await cmdDet2.ExecuteNonQueryAsync();
                }
            }
            tran.Commit();

            // Generar movimiento en promov/promovdet para cada entrada/producto recibido
            foreach (var idEntrada in entradasGeneradas)
            {
                try
                {
                    await using var cmdSp = conn.CreateCommand();
                    cmdSp.CommandText = "prtGenerarMovimientoEntrada";
                    cmdSp.CommandType = System.Data.CommandType.StoredProcedure;
                    cmdSp.Parameters.AddWithValue("@idEntradaCamion", idEntrada);
                    cmdSp.Parameters.AddWithValue("@Usuario", usuarioRecepcion);
                    await cmdSp.ExecuteNonQueryAsync();
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error al generar movimiento de inventario en promov para {IdEntrada}", idEntrada);
                }
            }

            return secuenciaGenerada;
        }
        catch
        {
            tran.Rollback();
            throw;
        }
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
        cmd.Parameters.AddWithValue("@idAlmacen",       (object?)filtros.IdAlmacen      ?? DBNull.Value);
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
        cmd.CommandText = @"SELECT e.*, 
                COALESCE(
                    e.OrdenNumero,
                    (SELECT TOP 1 o.Numero FROM ocOrdenes o WHERE o.idOrden = e.idOrden),
                    (SELECT TOP 1 r.OrdenNo FROM ocRecepcion r WHERE r.Recepcion = e.ProMov),
                    (SELECT TOP 1 r.OrdenNo FROM ocRecepcion r WHERE r.Nota = e.Conduce OR r.Referencia = e.Conduce)
                ) AS OrdenNumeroResolvido,
                ISNULL(e.idUnidad, (SELECT TOP 1 p.idUnidad FROM Producto p WHERE RTRIM(LTRIM(p.idProducto)) = RTRIM(LTRIM(e.idProducto)))) AS idUnidadFallback,
                0 AS TotalRegistros
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
            WHERE (e.Status = 'PENDIENTE' OR CAST(e.FechaEntrada AS DATE) = CAST(GETDATE() AS DATE))
                AND e.Status != 'CANCELADO'
              AND (@idPuerta IS NULL OR e.idPuerta = @idPuerta)
              AND (@usuarioPermiso IS NULL OR e.idAlmacen IS NULL OR e.idAlmacen IN (SELECT idAlmacen FROM AlmacenPermiso WHERE idSegUserGrp = @usuarioPermiso))
            ORDER BY CASE WHEN e.Status = 'PENDIENTE' THEN 0 ELSE 1 END, e.FechaEntrada DESC";
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
            Almacen          = HasColumn(r, "Almacen") ? GetStr(r, "Almacen") : GetStr(r, "idAlmacen"),
            Status           = r.GetString(r.GetOrdinal("Status")),
            IdOrden          = Get<Guid>(r, "idOrden"),
            OrdenNumero      = HasColumn(r, "OrdenNumeroResolvido") ? (Get<int>(r, "OrdenNumeroResolvido") ?? Get<int>(r, "OrdenNumero")) : Get<int>(r, "OrdenNumero"),
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

    
    public async Task<List<TicketProductoDto>> ObtenerProductosTicketAsync(Guid idEntradaCamion, string? conduceTransporte, string conduce, string? placa, DateTime fechaEntrada)
    {
        var lista = new List<TicketProductoDto>();
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        if (!string.IsNullOrWhiteSpace(conduceTransporte))
        {
            cmd.CommandText = @"
                SELECT idEntradaCamion, idProducto, Producto, CantidadRecibida, idUnidad, CantidadDeclarada, CantidadAlmacen, idUnidadAlmacen,
                       COALESCE(
                           OrdenNumero,
                           (SELECT TOP 1 o.Numero FROM ocOrdenes o WHERE o.idOrden = prtEntradaCamion.idOrden),
                           (SELECT TOP 1 r.OrdenNo FROM ocRecepcion r WHERE r.Recepcion = prtEntradaCamion.ProMov),
                           (SELECT TOP 1 r.OrdenNo FROM ocRecepcion r WHERE r.Nota = prtEntradaCamion.Conduce OR r.Referencia = prtEntradaCamion.Conduce)
                       ) AS OrdenNumero
                FROM prtEntradaCamion
                WHERE ConduceTransporte = @ct AND Status != 'CANCELADO'
                ORDER BY FechaCreacion, idEntradaCamion";
            cmd.Parameters.AddWithValue("@ct", conduceTransporte.Trim());
        }
        else
        {
            cmd.CommandText = @"
                SELECT idEntradaCamion, idProducto, Producto, CantidadRecibida, idUnidad, CantidadDeclarada, CantidadAlmacen, idUnidadAlmacen,
                       COALESCE(
                           OrdenNumero,
                           (SELECT TOP 1 o.Numero FROM ocOrdenes o WHERE o.idOrden = prtEntradaCamion.idOrden),
                           (SELECT TOP 1 r.OrdenNo FROM ocRecepcion r WHERE r.Recepcion = prtEntradaCamion.ProMov),
                           (SELECT TOP 1 r.OrdenNo FROM ocRecepcion r WHERE r.Nota = prtEntradaCamion.Conduce OR r.Referencia = prtEntradaCamion.Conduce)
                       ) AS OrdenNumero
                FROM prtEntradaCamion
                WHERE (idEntradaCamion = @id OR (Conduce = @c AND (@placa IS NULL OR Placa = @placa) AND CAST(FechaEntrada AS DATE) = CAST(@fe AS DATE)))
                  AND Status != 'CANCELADO'
                ORDER BY FechaCreacion, idEntradaCamion";
            cmd.Parameters.AddWithValue("@id", idEntradaCamion);
            cmd.Parameters.AddWithValue("@c", conduce);
            cmd.Parameters.AddWithValue("@placa", (object?)placa ?? DBNull.Value);
            cmd.Parameters.AddWithValue("@fe", fechaEntrada);
        }

        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            lista.Add(new TicketProductoDto
            {
                IdProducto        = reader["idProducto"] as string,
                Producto          = reader["Producto"]?.ToString() ?? "",
                CantidadDeclarada = reader["CantidadDeclarada"] as decimal?,
                CantidadRecibida  = reader["CantidadRecibida"] as decimal?,
                IdUnidad          = reader["idUnidad"] as string,
                CantidadAlmacen   = reader["CantidadAlmacen"] as decimal?,
                IdUnidadAlmacen   = reader["idUnidadAlmacen"] as string,
                OrdenNumero       = reader["OrdenNumero"] as int?
            });
        }

        if (lista.Count == 0)
        {
            await using var cmdDet = conn.CreateCommand();
            cmdDet.CommandText = @"
                SELECT idProducto, Producto, Cantidad, idUnidad
                FROM prtEntradaDetalle
                WHERE idEntradaCamion = @id
                ORDER BY Orden, idEntradaDetalle";
            cmdDet.Parameters.AddWithValue("@id", idEntradaCamion);
            await using var rDet = await cmdDet.ExecuteReaderAsync();
            while (await rDet.ReadAsync())
            {
                lista.Add(new TicketProductoDto
                {
                    IdProducto       = rDet["idProducto"] as string,
                    Producto         = rDet["Producto"]?.ToString() ?? "",
                    CantidadRecibida = rDet["Cantidad"] as decimal?,
                    IdUnidad         = rDet["idUnidad"] as string
                });
            }
        }

        return lista;
    }

    public async Task<List<ChoferDto>> BuscarChoferesAsync(string q)
    {
        var lista = new List<ChoferDto>();
        if (string.IsNullOrWhiteSpace(q) || q.Trim().Length < 2) return lista;
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = @"
            SELECT TOP 30
                c.idTransportistaChofer,
                c.TransportistaChofer AS NombreChofer,
                c.LicenciaNo,
                c.Celular,
                t.Transportista AS TransportistaNombre
            FROM lgTransportistaChofer c
            LEFT JOIN lgTransportista t ON c.idTransportista = t.idTransportista
            WHERE c.TransportistaChofer LIKE '%' + @q + '%'
              AND c.Status = 'ACTIVO' AND c.TransportistaChofer NOT LIKE '%GENERIC%' AND ISNULL(c.idTransportista, '') <> 'GENERICO' AND ISNULL(t.Transportista, '') NOT LIKE '%GENERIC%'
            ORDER BY c.TransportistaChofer";
        cmd.Parameters.AddWithValue("@q", q.Trim());
        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            lista.Add(new ChoferDto
            {
                IdChofer   = Guid.Parse(reader["idTransportistaChofer"].ToString()!),
                Nombre     = reader["NombreChofer"].ToString()!,
                LicenciaNo = reader["LicenciaNo"] as string,
                Celular    = reader["Celular"] as string,
                TransportistaNombre = reader["TransportistaNombre"] as string
            });
        }
        return lista;
    }

    public async Task AsignarEvidenciaAsync(Guid idEntradaCamion, Guid idEvidencia)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = "UPDATE prtEntradaCamion SET idEvidencia = @idEv WHERE idEntradaCamion = @id";
        cmd.Parameters.AddWithValue("@id", idEntradaCamion);
        cmd.Parameters.AddWithValue("@idEv", idEvidencia);
        await cmd.ExecuteNonQueryAsync();
    }

    public async Task<System.Collections.Generic.List<string>> ListarUnidadesAsync()
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();
        await using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT idUnidad FROM Unidad ORDER BY idUnidad";
        var l = new System.Collections.Generic.List<string>();
        await using var r = await cmd.ExecuteReaderAsync();
        while(await r.ReadAsync()) l.Add(r[0].ToString()!);
        return l;
    }

    public async Task<(string? identificador, string? revision)> ObtenerParametrosIsoAsync()
    {
        try {
            await using var conn = _cf.CreateErpConnection(); await conn.OpenAsync();
            await using var cmd = conn.CreateCommand(); cmd.CommandText = "SELECT Clave, CAST(Valor AS VARCHAR(100)) as ValorStr FROM defaults WHERE Categoria = 'ISO'";
            string? ident = null; string? rev = null;
            using var r = await cmd.ExecuteReaderAsync();
            while (await r.ReadAsync()) {
                var clave = r["Clave"]?.ToString()?.Trim().ToUpperInvariant();
                var val = r["ValorStr"]?.ToString()?.Trim();
                if (clave == "IDENTIFICADOR" || clave == "ISO_IDENT" || clave == "DOC_ID" || clave == "CODIGO") ident = val;
                else if (clave == "REVISION" || clave == "ISO_REV" || clave == "REV") rev = val;
            }
            return (ident ?? "FE-GC-02", rev ?? "03");
        } catch { return ("FE-GC-02", "03"); }
    }

    public async Task<string?> ObtenerNombreEmpresaAsync()
    {
        try {
            await using var conn = _cf.CreateErpConnection(); await conn.OpenAsync();
            await using var cmd = conn.CreateCommand(); cmd.CommandText = "SELECT TOP 1 companiacorto FROM Configuracion WHERE ISNULL(companiacorto, '') != ''";
            var result = await cmd.ExecuteScalarAsync();
            if (result != null && !string.IsNullOrWhiteSpace(result.ToString())) return result.ToString();
            cmd.CommandText = "SELECT TOP 1 Nombre FROM Companias WHERE ISNULL(Nombre, '') != ''";
            var resultComp = await cmd.ExecuteScalarAsync();
            return resultComp?.ToString() ?? "VMO CONCRETOS";
        } catch { return "VMO CONCRETOS"; }
    }

    // ─── Módulo de Conciliación de Suplidores y Pagos ─────────────────────────────

    public async Task<ResultadoConciliacionDto> CompararConducesAsync(CompararConciliacionRequest req, string usuario)
    {
        var itemsResult = new List<ResultadoItemConciliacionDto>();
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        var setConducesEnArchivo = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var item in req.Items)
        {
            var conduceNorm = (item.NoConduce ?? "").Trim();
            if (string.IsNullOrWhiteSpace(conduceNorm)) continue;

            // 1. Validar duplicado en el mismo archivo
            if (setConducesEnArchivo.Contains(conduceNorm))
            {
                itemsResult.Add(new ResultadoItemConciliacionDto
                {
                    FechaConduce      = item.Fecha,
                    NoConduce         = conduceNorm,
                    Producto          = item.Producto,
                    Mina              = item.Mina,
                    Planta            = item.Planta,
                    CantidadDeclarada = item.Cantidad,
                    PrecioUnitario    = item.Precio,
                    TotalReclamado    = item.Total > 0 ? item.Total : Math.Round(item.Cantidad * item.Precio, 2),
                    EstadoCuadre      = "NO_CALIFICA",
                    MotivoRechazo     = "Conduce duplicado en el mismo archivo Excel del suplidor.",
                    EstadoPago        = "RECHAZADO"
                });
                continue;
            }
            setConducesEnArchivo.Add(conduceNorm);

            // 2. Verificar si ya fue conciliado / pagado en otro lote
            await using var cmdVerif = conn.CreateCommand();
            cmdVerif.CommandText = @"
                SELECT TOP 1 l.NumeroConciliacion, d.EstadoPago, d.FechaPago
                FROM prtConciliacionDetalle d
                INNER JOIN prtConciliacionLote l ON d.idConciliacion = l.idConciliacion
                WHERE d.NoConduce = @c AND d.EstadoPago IN ('APROBADO', 'PAGADO')";
            cmdVerif.Parameters.AddWithValue("@c", conduceNorm);
            await using var rVerif = await cmdVerif.ExecuteReaderAsync();
            if (await rVerif.ReadAsync())
            {
                var numLote = rVerif["NumeroConciliacion"].ToString();
                var estPago = rVerif["EstadoPago"].ToString();
                rVerif.Close();

                itemsResult.Add(new ResultadoItemConciliacionDto
                {
                    FechaConduce      = item.Fecha,
                    NoConduce         = conduceNorm,
                    Producto          = item.Producto,
                    Mina              = item.Mina,
                    Planta            = item.Planta,
                    CantidadDeclarada = item.Cantidad,
                    PrecioUnitario    = item.Precio,
                    TotalReclamado    = item.Total > 0 ? item.Total : Math.Round(item.Cantidad * item.Precio, 2),
                    EstadoCuadre      = "NO_CALIFICA",
                    MotivoRechazo     = $"Conduce ya conciliado previamente en lote '{numLote}' con estado de pago '{estPago}'.",
                    EstadoPago        = "RECHAZADO"
                });
                continue;
            }
            rVerif.Close();

            // 3. Buscar entrada en prtEntradaCamion
            await using var cmd = conn.CreateCommand();
            cmd.CommandText = @"
                SELECT TOP 1
                    e.idEntradaCamion, e.Conduce, e.ConduceTransporte, e.idSuplidor, e.Suplidor,
                    e.idProducto, e.Producto, e.CantidadRecibida, e.CantidadAlmacen, e.idUnidad, e.idUnidadAlmacen,
                    e.idAlmacen, ISNULL(a.Almacen, e.idAlmacen) AS Almacen,
                    e.ProMov, e.Status, e.idOrden, e.OrdenNumero,
                    oc.Recepcion AS NumRecepcionOC,
                    od.Costo AS CostoOC, od.Descuento AS DescuentoOC
                FROM prtEntradaCamion e
                LEFT JOIN Almacen a ON a.idAlmacen = e.idAlmacen
                LEFT JOIN ocRecepcion oc ON e.ProMov = oc.Referencia AND oc.TipoReferencia = 'PRT'
                LEFT JOIN ocDetalleOrden od ON e.idOrden = od.idOrden 
                     AND (e.idProducto = od.idProducto OR od.idProducto = (SELECT TOP 1 p.idProducto FROM Producto p WHERE p.Producto = e.Producto))
                WHERE (e.Conduce = @conduce OR e.ConduceTransporte = @conduce)
                  AND (@idSuplidor IS NULL OR e.idSuplidor = @idSuplidor OR e.idSuplidor IS NULL)
                ORDER BY CASE 
                    WHEN e.Status = 'CERRADO' THEN 1 
                    WHEN e.Status = 'RECIBIDO' THEN 2 
                    WHEN e.Status = 'PENDIENTE' THEN 3 
                    ELSE 4 END";
            cmd.Parameters.AddWithValue("@conduce", conduceNorm);
            cmd.Parameters.AddWithValue("@idSuplidor", (object?)req.IdSuplidor ?? DBNull.Value);

            await using var reader = await cmd.ExecuteReaderAsync();
            if (!await reader.ReadAsync())
            {
                reader.Close();

                // Verificar si existe bajo otro suplidor
                await using var cmdOtro = conn.CreateCommand();
                cmdOtro.CommandText = "SELECT TOP 1 Suplidor FROM prtEntradaCamion WHERE Conduce = @conduce OR ConduceTransporte = @conduce";
                cmdOtro.Parameters.AddWithValue("@conduce", conduceNorm);
                var otroSup = await cmdOtro.ExecuteScalarAsync();

                string rechazoMsg = otroSup != null 
                    ? $"El conduce está registrado para otro suplidor ('{otroSup}')."
                    : "Conduce no encontrado en el sistema ni en Control de Puerta.";

                itemsResult.Add(new ResultadoItemConciliacionDto
                {
                    FechaConduce      = item.Fecha,
                    NoConduce         = conduceNorm,
                    Producto          = item.Producto,
                    Mina              = item.Mina,
                    Planta            = item.Planta,
                    CantidadDeclarada = item.Cantidad,
                    PrecioUnitario    = item.Precio,
                    TotalReclamado    = item.Total > 0 ? item.Total : Math.Round(item.Cantidad * item.Precio, 2),
                    EstadoCuadre      = "NO_CALIFICA",
                    MotivoRechazo     = rechazoMsg,
                    EstadoPago        = "RECHAZADO"
                });
                continue;
            }

            var idEntradaCamion = reader.GetGuid(reader.GetOrdinal("idEntradaCamion"));
            var proMov          = reader["ProMov"] as string;
            var numRecepcionOC  = reader["NumRecepcionOC"] as string;
            var ordenNumero     = reader.IsDBNull(reader.GetOrdinal("OrdenNumero")) ? null : (int?)reader.GetInt32(reader.GetOrdinal("OrdenNumero"));
            var idOrden         = reader.IsDBNull(reader.GetOrdinal("idOrden")) ? null : (Guid?)reader.GetGuid(reader.GetOrdinal("idOrden"));
            var productoSis     = reader["Producto"] as string;
            var plantaSis       = reader["Almacen"] as string ?? reader["idAlmacen"] as string;
            var statusSis       = reader["Status"]?.ToString() ?? "";
            var idUnidadSis     = reader["idUnidadAlmacen"] as string ?? reader["idUnidad"] as string ?? "Mts3";
            var cantRecibida    = reader.IsDBNull(reader.GetOrdinal("CantidadRecibida")) ? (decimal?)null : reader.GetDecimal(reader.GetOrdinal("CantidadRecibida"));
            var cantAlmacen     = reader.IsDBNull(reader.GetOrdinal("CantidadAlmacen")) ? (decimal?)null : reader.GetDecimal(reader.GetOrdinal("CantidadAlmacen"));
            var costoOC         = reader.IsDBNull(reader.GetOrdinal("CostoOC")) ? (decimal?)null : reader.GetDecimal(reader.GetOrdinal("CostoOC"));
            reader.Close();

            decimal cantFinalSis = cantAlmacen ?? cantRecibida ?? 0;
            decimal precioFinal = item.Precio > 0 ? item.Precio : (costoOC ?? 0);
            decimal totalReclamado = item.Total > 0 ? item.Total : Math.Round(item.Cantidad * item.Precio, 2);

            // Validar Estado de la Recepción
            if (statusSis.Equals("CANCELADO", StringComparison.OrdinalIgnoreCase) || statusSis.Equals("BLOQUEADO", StringComparison.OrdinalIgnoreCase))
            {
                itemsResult.Add(new ResultadoItemConciliacionDto
                {
                    FechaConduce       = item.Fecha,
                    NoConduce          = conduceNorm,
                    Producto           = item.Producto,
                    Mina               = item.Mina,
                    Planta             = item.Planta,
                    CantidadDeclarada  = item.Cantidad,
                    PrecioUnitario     = item.Precio,
                    TotalReclamado     = totalReclamado,
                    IdEntradaCamion    = idEntradaCamion,
                    ProMov             = proMov,
                    NumRecepcionOC     = numRecepcionOC,
                    OrdenNumero        = ordenNumero,
                    IdOrden            = idOrden,
                    ProductoEncontrado = productoSis,
                    PlantaEncontrada   = plantaSis,
                    CantidadSistema    = cantFinalSis,
                    UnidadSistema      = idUnidadSis,
                    PrecioSistema      = costoOC,
                    EstadoCuadre       = "NO_CALIFICA",
                    MotivoRechazo      = $"La recepción fue cancelada o bloqueada en planta ({statusSis}).",
                    EstadoPago         = "RECHAZADO"
                });
                continue;
            }

            if (statusSis.Equals("PENDIENTE", StringComparison.OrdinalIgnoreCase))
            {
                itemsResult.Add(new ResultadoItemConciliacionDto
                {
                    FechaConduce       = item.Fecha,
                    NoConduce          = conduceNorm,
                    Producto           = item.Producto,
                    Mina               = item.Mina,
                    Planta             = item.Planta,
                    CantidadDeclarada  = item.Cantidad,
                    PrecioUnitario     = item.Precio,
                    TotalReclamado     = totalReclamado,
                    IdEntradaCamion    = idEntradaCamion,
                    ProductoEncontrado = productoSis,
                    PlantaEncontrada   = plantaSis,
                    CantidadSistema    = cantFinalSis,
                    UnidadSistema      = idUnidadSis,
                    PrecioSistema      = costoOC,
                    EstadoCuadre       = "PENDIENTE_RECEPCION",
                    MotivoRechazo      = "Registrado en puerta pero aún pendiente de confirmar recepción física en planta.",
                    EstadoPago         = "PENDIENTE"
                });
                continue;
            }

            // Comparar Cantidades
            decimal diffCant = Math.Abs(item.Cantidad - cantFinalSis);
            if (diffCant > 0.05m)
            {
                itemsResult.Add(new ResultadoItemConciliacionDto
                {
                    FechaConduce       = item.Fecha,
                    NoConduce          = conduceNorm,
                    Producto           = item.Producto,
                    Mina               = item.Mina,
                    Planta             = item.Planta,
                    CantidadDeclarada  = item.Cantidad,
                    PrecioUnitario     = item.Precio,
                    TotalReclamado     = totalReclamado,
                    IdEntradaCamion    = idEntradaCamion,
                    ProMov             = proMov,
                    NumRecepcionOC     = numRecepcionOC,
                    OrdenNumero        = ordenNumero,
                    IdOrden            = idOrden,
                    ProductoEncontrado = productoSis,
                    PlantaEncontrada   = plantaSis,
                    CantidadSistema    = cantFinalSis,
                    UnidadSistema      = idUnidadSis,
                    PrecioSistema      = costoOC,
                    TotalAprobado      = Math.Round(cantFinalSis * precioFinal, 2),
                    EstadoCuadre       = "NO_CALIFICA",
                    MotivoRechazo      = $"Discrepancia en cantidad: Suplidor declara {item.Cantidad:N2} {idUnidadSis}, Planta recibió {cantFinalSis:N2} {idUnidadSis} (Diferencia: {diffCant:N2}).",
                    EstadoPago         = "RECHAZADO"
                });
                continue;
            }

            // Advertencia suave si la planta especificada no coincide
            string notasPlanta = "";
            if (!string.IsNullOrWhiteSpace(item.Planta) && !string.IsNullOrWhiteSpace(plantaSis))
            {
                if (!plantaSis.Contains(item.Planta.Trim(), StringComparison.OrdinalIgnoreCase) &&
                    !item.Planta.Contains(plantaSis.Trim(), StringComparison.OrdinalIgnoreCase))
                {
                    notasPlanta = $" (Nota: Planta declarada '{item.Planta}' vs Planta recibida '{plantaSis}')";
                }
            }

            // ¡Califica para Pago!
            decimal totalAprobado = Math.Round(cantFinalSis * (precioFinal > 0 ? precioFinal : 1), 2);
            itemsResult.Add(new ResultadoItemConciliacionDto
            {
                FechaConduce       = item.Fecha,
                NoConduce          = conduceNorm,
                Producto           = item.Producto,
                Mina               = item.Mina,
                Planta             = item.Planta,
                CantidadDeclarada  = item.Cantidad,
                PrecioUnitario     = item.Precio,
                TotalReclamado     = totalReclamado,
                IdEntradaCamion    = idEntradaCamion,
                ProMov             = proMov,
                NumRecepcionOC     = numRecepcionOC,
                OrdenNumero        = ordenNumero,
                IdOrden            = idOrden,
                ProductoEncontrado = productoSis,
                PlantaEncontrada   = plantaSis,
                CantidadSistema    = cantFinalSis,
                UnidadSistema      = idUnidadSis,
                PrecioSistema      = precioFinal,
                TotalAprobado      = totalAprobado,
                EstadoCuadre       = "CALIFICA_PAGO",
                MotivoRechazo      = "Conduce verificado y recibido en planta." + notasPlanta,
                EstadoPago         = "CALIFICA_PAGO"
            });
        }

        var totalCalifican = itemsResult.Count(i => i.EstadoCuadre == "CALIFICA_PAGO");
        var totalRechazados = itemsResult.Count(i => i.EstadoCuadre == "NO_CALIFICA");
        var totalPendientes = itemsResult.Count(i => i.EstadoCuadre == "PENDIENTE_RECEPCION");
        var montoReclamado  = itemsResult.Sum(i => i.TotalReclamado);
        var montoCalifica   = itemsResult.Where(i => i.EstadoCuadre == "CALIFICA_PAGO").Sum(i => i.TotalAprobado ?? i.TotalReclamado);

        return new ResultadoConciliacionDto
        {
            IdSuplidor          = req.IdSuplidor,
            Suplidor            = req.Suplidor,
            NombreArchivo       = req.NombreArchivo,
            Usuario             = usuario,
            TotalConduces       = itemsResult.Count,
            TotalCalifican      = totalCalifican,
            TotalRechazados     = totalRechazados,
            TotalPendientes     = totalPendientes,
            MontoTotalReclamado = montoReclamado,
            MontoTotalCalifica  = montoCalifica,
            Items               = itemsResult
        };
    }

    public async Task<Guid> GuardarLoteConciliacionAsync(GuardarConciliacionRequest req, string usuario)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();
        await using var tran = conn.BeginTransaction();

        try
        {
            var idConciliacion = Guid.NewGuid();

            // Generar número de conciliación secuencial: CONC-YYYYMM-XXXX
            var prefix = $"CONC-{DateTime.Now:yyyyMM}-";
            await using var cmdSeq = conn.CreateCommand();
            cmdSeq.Transaction = tran;
            cmdSeq.CommandText = "SELECT COUNT(*) + 1 FROM prtConciliacionLote WHERE NumeroConciliacion LIKE @pref + '%'";
            cmdSeq.Parameters.AddWithValue("@pref", prefix);
            var nextSeq = Convert.ToInt32(await cmdSeq.ExecuteScalarAsync() ?? 1);
            var numConciliacion = $"{prefix}{nextSeq:D4}";

            var totalCalifican  = req.Items.Count(i => i.EstadoCuadre == "CALIFICA_PAGO");
            var totalRechazados = req.Items.Count(i => i.EstadoCuadre == "NO_CALIFICA");
            var totalPendientes = req.Items.Count(i => i.EstadoCuadre == "PENDIENTE_RECEPCION");
            var montoReclamado  = req.Items.Sum(i => i.TotalReclamado);
            var montoCalifica   = req.Items.Where(i => i.EstadoCuadre == "CALIFICA_PAGO").Sum(i => i.TotalAprobado ?? i.TotalReclamado);

            // 1. Insertar Lote
            await using var cmdLote = conn.CreateCommand();
            cmdLote.Transaction = tran;
            cmdLote.CommandText = @"
                INSERT INTO prtConciliacionLote (
                    idConciliacion, NumeroConciliacion, idSuplidor, Suplidor,
                    FechaCarga, Usuario, NombreArchivo, TotalConduces, TotalCalifican,
                    TotalRechazados, TotalPendientes, MontoTotalReclamado, MontoTotalCalifica,
                    Status, Notas
                )
                VALUES (
                    @id, @num, @idSup, @sup, GETDATE(), @usr, @archivo, @tot, @cal,
                    @rech, @pend, @montoRec, @montoCal, 'REVISADO', @notas
                )";
            cmdLote.Parameters.AddWithValue("@id", idConciliacion);
            cmdLote.Parameters.AddWithValue("@num", numConciliacion);
            cmdLote.Parameters.AddWithValue("@idSup", (object?)req.IdSuplidor ?? DBNull.Value);
            cmdLote.Parameters.AddWithValue("@sup", req.Suplidor);
            cmdLote.Parameters.AddWithValue("@usr", usuario);
            cmdLote.Parameters.AddWithValue("@archivo", (object?)req.NombreArchivo ?? DBNull.Value);
            cmdLote.Parameters.AddWithValue("@tot", req.Items.Count);
            cmdLote.Parameters.AddWithValue("@cal", totalCalifican);
            cmdLote.Parameters.AddWithValue("@rech", totalRechazados);
            cmdLote.Parameters.AddWithValue("@pend", totalPendientes);
            cmdLote.Parameters.AddWithValue("@montoRec", montoReclamado);
            cmdLote.Parameters.AddWithValue("@montoCal", montoCalifica);
            cmdLote.Parameters.AddWithValue("@notas", (object?)req.Notas ?? DBNull.Value);
            await cmdLote.ExecuteNonQueryAsync();

            // 2. Insertar Detalles
            foreach (var item in req.Items)
            {
                await using var cmdDet = conn.CreateCommand();
                cmdDet.Transaction = tran;
                cmdDet.CommandText = @"
                    INSERT INTO prtConciliacionDetalle (
                        idDetalle, idConciliacion, FechaConduce, NoConduce, Producto, Mina, Planta,
                        CantidadDeclarada, PrecioUnitario, TotalReclamado, idEntradaCamion, ProMov,
                        NumRecepcionOC, OrdenNumero, idOrden, ProductoEncontrado, PlantaEncontrada,
                        CantidadSistema, UnidadSistema, PrecioSistema, TotalAprobado, EstadoCuadre,
                        MotivoRechazo, EstadoPago, Notas
                    )
                    VALUES (
                        NEWID(), @idLote, @fecha, @conduce, @prod, @mina, @planta,
                        @cantDec, @precio, @totRec, @idEntrada, @promov,
                        @numRec, @ordNum, @idOrd, @prodEnc, @plantaEnc,
                        @cantSis, @uSis, @precioSis, @totAprob, @estCuadre,
                        @motivo, @estPago, @notas
                    )";
                cmdDet.Parameters.AddWithValue("@idLote", idConciliacion);
                cmdDet.Parameters.AddWithValue("@fecha", (object?)item.FechaConduce ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@conduce", item.NoConduce);
                cmdDet.Parameters.AddWithValue("@prod", (object?)item.Producto ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@mina", (object?)item.Mina ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@planta", (object?)item.Planta ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@cantDec", item.CantidadDeclarada);
                cmdDet.Parameters.AddWithValue("@precio", item.PrecioUnitario);
                cmdDet.Parameters.AddWithValue("@totRec", item.TotalReclamado);
                cmdDet.Parameters.AddWithValue("@idEntrada", (object?)item.IdEntradaCamion ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@promov", (object?)item.ProMov ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@numRec", (object?)item.NumRecepcionOC ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@ordNum", (object?)item.OrdenNumero ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@idOrd", (object?)item.IdOrden ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@prodEnc", (object?)item.ProductoEncontrado ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@plantaEnc", (object?)item.PlantaEncontrada ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@cantSis", (object?)item.CantidadSistema ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@uSis", (object?)item.UnidadSistema ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@precioSis", (object?)item.PrecioSistema ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@totAprob", (object?)item.TotalAprobado ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@estCuadre", item.EstadoCuadre);
                cmdDet.Parameters.AddWithValue("@motivo", (object?)item.MotivoRechazo ?? DBNull.Value);
                cmdDet.Parameters.AddWithValue("@estPago", item.EstadoPago);
                cmdDet.Parameters.AddWithValue("@notas", (object?)item.Notas ?? DBNull.Value);
                await cmdDet.ExecuteNonQueryAsync();
            }

            await tran.CommitAsync();
            return idConciliacion;
        }
        catch
        {
            await tran.RollbackAsync();
            throw;
        }
    }

    public async Task<List<LoteConciliacionDto>> ListarLotesConciliacionAsync(string? idSuplidor, string? status)
    {
        var lista = new List<LoteConciliacionDto>();
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        await using var cmd = conn.CreateCommand();
        cmd.CommandText = "prtListarLotesConciliacion";
        cmd.CommandType = System.Data.CommandType.StoredProcedure;
        cmd.Parameters.AddWithValue("@idSuplidor", (object?)idSuplidor ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@Status", (object?)status ?? DBNull.Value);

        await using var r = await cmd.ExecuteReaderAsync();
        while (await r.ReadAsync())
        {
            lista.Add(new LoteConciliacionDto
            {
                IdConciliacion      = r.GetGuid(r.GetOrdinal("idConciliacion")),
                NumeroConciliacion  = r["NumeroConciliacion"].ToString()!,
                IdSuplidor          = r["idSuplidor"] as string,
                Suplidor            = r["Suplidor"].ToString()!,
                FechaCarga          = r.GetDateTime(r.GetOrdinal("FechaCarga")),
                Usuario             = r["Usuario"].ToString()!,
                NombreArchivo       = r["NombreArchivo"] as string,
                TotalConduces       = r.GetInt32(r.GetOrdinal("TotalConduces")),
                TotalCalifican      = r.GetInt32(r.GetOrdinal("TotalCalifican")),
                TotalRechazados     = r.GetInt32(r.GetOrdinal("TotalRechazados")),
                TotalPendientes     = r.GetInt32(r.GetOrdinal("TotalPendientes")),
                MontoTotalReclamado = r.GetDecimal(r.GetOrdinal("MontoTotalReclamado")),
                MontoTotalCalifica  = r.GetDecimal(r.GetOrdinal("MontoTotalCalifica")),
                Status              = r["Status"].ToString()!,
                FechaAprobacion     = r.IsDBNull(r.GetOrdinal("FechaAprobacion")) ? null : r.GetDateTime(r.GetOrdinal("FechaAprobacion")),
                UsuarioAprobacion   = r["UsuarioAprobacion"] as string,
                Notas               = r["Notas"] as string
            });
        }
        return lista;
    }

    public async Task<ResultadoConciliacionDto?> ObtenerLoteConciliacionAsync(Guid idConciliacion)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();

        // 1. Obtener cabecera
        await using var cmdLote = conn.CreateCommand();
        cmdLote.CommandText = "SELECT * FROM prtConciliacionLote WHERE idConciliacion = @id";
        cmdLote.Parameters.AddWithValue("@id", idConciliacion);
        await using var rLote = await cmdLote.ExecuteReaderAsync();
        if (!await rLote.ReadAsync()) return null;

        var dto = new ResultadoConciliacionDto
        {
            IdConciliacion      = rLote.GetGuid(rLote.GetOrdinal("idConciliacion")),
            NumeroConciliacion  = rLote["NumeroConciliacion"].ToString()!,
            IdSuplidor          = rLote["idSuplidor"] as string,
            Suplidor            = rLote["Suplidor"].ToString()!,
            FechaCarga          = rLote.GetDateTime(rLote.GetOrdinal("FechaCarga")),
            Usuario             = rLote["Usuario"].ToString()!,
            NombreArchivo       = rLote["NombreArchivo"] as string,
            TotalConduces       = rLote.GetInt32(rLote.GetOrdinal("TotalConduces")),
            TotalCalifican      = rLote.GetInt32(rLote.GetOrdinal("TotalCalifican")),
            TotalRechazados     = rLote.GetInt32(rLote.GetOrdinal("TotalRechazados")),
            TotalPendientes     = rLote.GetInt32(rLote.GetOrdinal("TotalPendientes")),
            MontoTotalReclamado = rLote.GetDecimal(rLote.GetOrdinal("MontoTotalReclamado")),
            MontoTotalCalifica  = rLote.GetDecimal(rLote.GetOrdinal("MontoTotalCalifica")),
            Status              = rLote["Status"].ToString()!,
            FechaAprobacion     = rLote.IsDBNull(rLote.GetOrdinal("FechaAprobacion")) ? null : rLote.GetDateTime(rLote.GetOrdinal("FechaAprobacion")),
            UsuarioAprobacion   = rLote["UsuarioAprobacion"] as string,
            Notas               = rLote["Notas"] as string
        };
        rLote.Close();

        // 2. Obtener detalles
        await using var cmdDet = conn.CreateCommand();
        cmdDet.CommandText = "prtObtenerDetalleConciliacion";
        cmdDet.CommandType = System.Data.CommandType.StoredProcedure;
        cmdDet.Parameters.AddWithValue("@idConciliacion", idConciliacion);

        await using var rDet = await cmdDet.ExecuteReaderAsync();
        var items = new List<ResultadoItemConciliacionDto>();
        while (await rDet.ReadAsync())
        {
            items.Add(new ResultadoItemConciliacionDto
            {
                IdDetalle          = rDet.GetGuid(rDet.GetOrdinal("idDetalle")),
                FechaConduce       = rDet.IsDBNull(rDet.GetOrdinal("FechaConduce")) ? null : rDet.GetDateTime(rDet.GetOrdinal("FechaConduce")),
                NoConduce          = rDet["NoConduce"].ToString()!,
                Producto           = rDet["Producto"] as string,
                Mina               = rDet["Mina"] as string,
                Planta             = rDet["Planta"] as string,
                CantidadDeclarada  = rDet.GetDecimal(rDet.GetOrdinal("CantidadDeclarada")),
                PrecioUnitario     = rDet.GetDecimal(rDet.GetOrdinal("PrecioUnitario")),
                TotalReclamado     = rDet.GetDecimal(rDet.GetOrdinal("TotalReclamado")),
                IdEntradaCamion    = rDet.IsDBNull(rDet.GetOrdinal("idEntradaCamion")) ? null : rDet.GetGuid(rDet.GetOrdinal("idEntradaCamion")),
                ProMov             = rDet["ProMov"] as string,
                NumRecepcionOC     = rDet["NumRecepcionOC"] as string,
                OrdenNumero        = rDet.IsDBNull(rDet.GetOrdinal("OrdenNumero")) ? null : rDet.GetInt32(rDet.GetOrdinal("OrdenNumero")),
                IdOrden            = rDet.IsDBNull(rDet.GetOrdinal("idOrden")) ? null : rDet.GetGuid(rDet.GetOrdinal("idOrden")),
                ProductoEncontrado = rDet["ProductoEncontrado"] as string,
                PlantaEncontrada   = rDet["PlantaEncontrada"] as string,
                CantidadSistema    = rDet.IsDBNull(rDet.GetOrdinal("CantidadSistema")) ? null : rDet.GetDecimal(rDet.GetOrdinal("CantidadSistema")),
                UnidadSistema      = rDet["UnidadSistema"] as string,
                PrecioSistema      = rDet.IsDBNull(rDet.GetOrdinal("PrecioSistema")) ? null : rDet.GetDecimal(rDet.GetOrdinal("PrecioSistema")),
                TotalAprobado      = rDet.IsDBNull(rDet.GetOrdinal("TotalAprobado")) ? null : rDet.GetDecimal(rDet.GetOrdinal("TotalAprobado")),
                EstadoCuadre       = rDet["EstadoCuadre"].ToString()!,
                MotivoRechazo      = rDet["MotivoRechazo"] as string,
                EstadoPago         = rDet["EstadoPago"].ToString()!,
                FechaPago          = rDet.IsDBNull(rDet.GetOrdinal("FechaPago")) ? null : rDet.GetDateTime(rDet.GetOrdinal("FechaPago")),
                ReferenciaPago     = rDet["ReferenciaPago"] as string,
                Notas              = rDet["Notas"] as string
            });
        }
        return dto with { Items = items };
    }

    public async Task<bool> ActualizarEstadoPagoLoteAsync(Guid idConciliacion, ActualizarEstadoPagoRequest req, string usuario)
    {
        await using var conn = _cf.CreateErpConnection();
        await conn.OpenAsync();
        await using var tran = conn.BeginTransaction();

        try
        {
            // 1. Actualizar detalles específicos o todos los que califican
            await using var cmdDet = conn.CreateCommand();
            cmdDet.Transaction = tran;

            string idsFilter = "";
            if (req.IdsDetalle != null && req.IdsDetalle.Count > 0)
            {
                var idStrings = string.Join(",", req.IdsDetalle.Select(id => $"'{id}'"));
                idsFilter = $"AND idDetalle IN ({idStrings})";
            }
            else
            {
                // Si no se pasaron IDs específicos, aplica a los que califican para pago
                idsFilter = "AND EstadoCuadre = 'CALIFICA_PAGO'";
            }

            cmdDet.CommandText = $@"
                UPDATE prtConciliacionDetalle
                SET EstadoPago = @est,
                    ReferenciaPago = ISNULL(@ref, ReferenciaPago),
                    FechaPago = CASE WHEN @est = 'PAGADO' THEN GETDATE() ELSE FechaPago END,
                    Notas = CASE WHEN @notas IS NOT NULL THEN ISNULL(Notas, '') + ' ' + @notas ELSE Notas END
                WHERE idConciliacion = @idLote {idsFilter}";
            cmdDet.Parameters.AddWithValue("@est", req.NuevoEstadoPago);
            cmdDet.Parameters.AddWithValue("@ref", (object?)req.ReferenciaPago ?? DBNull.Value);
            cmdDet.Parameters.AddWithValue("@notas", (object?)req.Notas ?? DBNull.Value);
            cmdDet.Parameters.AddWithValue("@idLote", idConciliacion);
            await cmdDet.ExecuteNonQueryAsync();

            // 2. Actualizar estado general del Lote
            await using var cmdLote = conn.CreateCommand();
            cmdLote.Transaction = tran;
            if (req.NuevoEstadoPago == "APROBADO")
            {
                cmdLote.CommandText = @"
                    UPDATE prtConciliacionLote
                    SET Status = 'APROBADO_PAGO',
                        FechaAprobacion = GETDATE(),
                        UsuarioAprobacion = @usr
                    WHERE idConciliacion = @idLote";
            }
            else if (req.NuevoEstadoPago == "PAGADO")
            {
                cmdLote.CommandText = @"
                    UPDATE prtConciliacionLote
                    SET Status = 'PAGADO'
                    WHERE idConciliacion = @idLote";
            }
            else
            {
                cmdLote.CommandText = @"
                    UPDATE prtConciliacionLote
                    SET Status = @est
                    WHERE idConciliacion = @idLote";
                cmdLote.Parameters.AddWithValue("@est", req.NuevoEstadoPago);
            }
            cmdLote.Parameters.AddWithValue("@usr", usuario);
            cmdLote.Parameters.AddWithValue("@idLote", idConciliacion);
            await cmdLote.ExecuteNonQueryAsync();

            await tran.CommitAsync();
            return true;
        }
        catch
        {
            await tran.RollbackAsync();
            throw;
        }
    }
}
