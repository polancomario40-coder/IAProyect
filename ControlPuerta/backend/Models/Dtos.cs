namespace ControlPuertaAPI.Models;

// ─── Request DTOs ─────────────────────────────────────────────────────────────

public record OcrPlacaRequest(
    string ImagenBase64,        // Base64 de la imagen (sin prefijo data:image/...)
    string MimeType = "image/jpeg"
);

public record ValidarTransportistaRequest(string Placa);

public record RegistrarEntradaRequest
{
    public string   Conduce             { get; init; } = "";
    public string   Placa               { get; init; } = "";
    public string?  PlacaOcrTexto       { get; init; }
    public decimal? PlacaOcrConfianza   { get; init; }
    public string?  FotoPlacaBase64     { get; init; }
    public string?  FotoPlacaMime       { get; init; }
    public string?  IdTransportista     { get; init; }
    public string?  Transportista       { get; init; }
    public Guid?    IdChofer            { get; init; }
    public string?  NombreChofer        { get; init; }
    public string?  IdProducto          { get; init; }
    public string?  Producto            { get; init; }
    public string?  IdAlmacen           { get; init; }
    public string?  IdPuerta            { get; init; }
    public string?  Notas               { get; init; }
    public decimal? CantidadDeclarada   { get; init; }
    public List<ProductoDetalleRequest> Productos { get; init; } = new();
}

public record ProductoDetalleRequest
{
    public string?  IdProducto  { get; init; }
    public string?  Producto    { get; init; }
    public decimal? Cantidad    { get; init; }
    public string?  IdUnidad    { get; init; }
    public string?  Notas       { get; init; }
}

public record ConfirmarRecepcionRequest
{
    public Guid     IdEntradaCamion     { get; init; }
    public string   Conduce             { get; init; } = "";
    public string?  ConduceTransporte   { get; init; }
    public string?  IdSuplidor          { get; init; }
    public string?  NombreSuplidor      { get; init; }
    public string?  IdAlmacen           { get; init; }
    public List<ProductoRecepcionDto> Productos { get; init; } = new();
    public string?  Notas               { get; init; }
    // Evidencias en base64
    public string?  FotoConduceBase64   { get; init; }
    public string?  FotoConduceMime     { get; init; } = "image/jpeg";
    public string?  FotoConduceNombre   { get; init; }
    public string?  FirmaDigitalBase64  { get; init; }
    public string?  ImagenFirmadaBase64 { get; init; }
    public string?  FotoCamionBase64    { get; init; }
}

public record ProductoRecepcionDto
{
    public string?  IdProductoReal      { get; init; }
    public string?  NombreProductoReal  { get; init; }
    public decimal  CantidadRecibida    { get; init; }
    public string?  IdUnidad            { get; init; }
    public string?  IdUnidadAlmacen     { get; init; }
    public decimal? CantidadAlmacen     { get; init; }
}

public record ProductoDto
{
    public string  IdProductoPuerta { get; init; } = "";
    public string  IdProducto       { get; init; } = "";
    public string  Nombre           { get; init; } = "";
    public string? IdUnidad         { get; init; }
}

public record SuplidorDto
{
    public string IdSuplidor { get; init; } = "";
    public string Nombre     { get; init; } = "";
}

public record AlmacenDto
{
    public string IdAlmacen { get; init; } = "";
    public string Nombre    { get; init; } = "";
}

public record AsignarOcRequest
{
    public Guid   IdEntradaCamion  { get; init; }
    public Guid   IdOrden          { get; init; }
    public int    OrdenNumero      { get; init; }
    public int    EvalCalidad      { get; init; } = 255;
    public int    EvalTiempo       { get; init; } = 255;
    public int    EvalServicio     { get; init; } = 255;
}

public record EjecutarCierreRequest
{
    public DateOnly FechaDia    { get; init; }
    public string?  Notas       { get; init; }
    public List<AsignarOcRequest> AsignacionesOc { get; init; } = new();
}

public record ConsultaFiltros
{
    public DateOnly? FechaDesde     { get; init; }
    public DateOnly? FechaHasta     { get; init; }
    public string?   Conduce        { get; init; }
    public string?   Placa          { get; init; }
    public string?   Transportista  { get; init; }
    public string?   Status         { get; init; }
    public string?   IdAlmacen      { get; init; }
    public int       PageNumber     { get; init; } = 1;
    public int       PageSize       { get; init; } = 50;
    
    public string?   UsuarioPermiso { get; set; }
}

// ─── Response DTOs ────────────────────────────────────────────────────────────

public record OcrPlacaResponse(
    bool    Exito,
    string  TextoDetectado,
    decimal Confianza,
    string? Mensaje = null
);

public record TransportistaDto
{
    public string  IdTransportista          { get; init; } = "";
    public string  Nombre                   { get; init; } = "";
    public string? Telefono                 { get; init; }
    public string  Status                   { get; init; } = "";
    public Guid    IdEquipo                 { get; init; }
    public string  PlacaNo                  { get; init; } = "";
    public DateTime? PlacaVence             { get; init; }
    public string? NombreEquipo             { get; init; }
    public decimal? Capacidad               { get; init; }
    public string?  IdUnidad                { get; init; }
    public List<ChoferDto> Choferes         { get; init; } = new();
}

public record ChoferDto
{
    public Guid    IdChofer     { get; init; }
    public string  Nombre       { get; init; } = "";
    public string? LicenciaNo   { get; init; }
    public string?   TransportistaNombre { get; init; }
    public string?   Celular          { get; init; }
}

public record EntradaCamionDto
{
    public Guid      IdEntradaCamion     { get; init; }
    public string    Conduce             { get; init; } = "";
    public string?   ConduceTransporte   { get; init; }
    public string    Placa               { get; init; } = "";
    public string?   IdTransportista     { get; init; }
    public string?   Transportista       { get; init; }
    public Guid?     IdChofer            { get; init; }
    public string?   NombreChofer        { get; init; }
    public DateTime  FechaEntrada        { get; init; }
    public DateTime? FechaRecepcion      { get; init; }
    public string?   UsuarioRecepcion    { get; init; }
    public string?   IdProducto          { get; init; }
    public string?   Producto            { get; init; }
    public string?   IdSuplidor          { get; init; }
    public string?   Suplidor            { get; init; }
    public decimal?  CantidadDeclarada   { get; init; }
    public decimal?  CantidadRecibida    { get; init; }
    public string?   IdUnidad            { get; init; }
    public string?   IdUnidadAlmacen     { get; init; }
    public decimal?  CantidadAlmacen     { get; init; }
    public string?   IdAlmacen           { get; init; }
    public string?   Almacen             { get; init; }
    public string    Status              { get; init; } = "";
    public Guid?     IdOrden             { get; init; }
    public int?      OrdenNumero         { get; init; }
    public Guid?     IdEvidencia         { get; init; }
    public string?   Notas               { get; init; }
    public string    Usuario             { get; init; } = "";
    public string?   IdPuerta            { get; init; }
    public string?   ProMov              { get; init; }
    public string?   NumRecepcionOC      { get; init; }
    public int       TotalRegistros      { get; init; }
}

public record CierreDiaResultDto
{
    public Guid    IdCierre            { get; init; }
    public DateOnly FechaDia           { get; init; }
    public int     TotalRecepciones    { get; init; }
    public int     TotalConOC          { get; init; }
    public int     TotalSinOC          { get; init; }
}

public record ApiResponse<T>
{
    public bool   Success { get; init; }
    public string Mensaje { get; init; } = "";
    public T?     Data    { get; init; }

    public static ApiResponse<T> Ok(T data, string mensaje = "Operación exitosa.")
        => new() { Success = true, Mensaje = mensaje, Data = data };

    public static ApiResponse<T> Fail(string mensaje)
        => new() { Success = false, Mensaje = mensaje, Data = default };
}

public record TicketProductoDto
{
    public string?  IdProducto        { get; init; }
    public string   Producto          { get; init; } = "";
    public decimal? CantidadDeclarada { get; init; }
    public decimal? CantidadRecibida  { get; init; }
    public string?  IdUnidad          { get; init; }
    public decimal? CantidadAlmacen   { get; init; }
    public string?  IdUnidadAlmacen   { get; init; }
    public int?     OrdenNumero       { get; init; }
}

// ─── Módulo de Conciliación de Suplidores y Pagos ─────────────────────────────

public record ItemConciliacionInputDto
{
    public DateTime? Fecha            { get; init; }
    public string    NoConduce        { get; init; } = "";
    public string?   Producto         { get; init; }
    public string?   Mina             { get; init; }
    public string?   Planta           { get; init; }
    public decimal   Cantidad         { get; init; }
    public decimal   Precio           { get; init; }
    public decimal   Total            { get; init; }
}

public record ExtraerDocumentoRequest
{
    public string?   Base64           { get; init; }
    public string?   MimeType         { get; init; }
    public string?   NombreArchivo    { get; init; }
}

public record CompararConciliacionRequest
{
    public string?   IdSuplidor       { get; init; }
    public string    Suplidor         { get; init; } = "";
    public string?   NombreArchivo    { get; init; }
    public List<ItemConciliacionInputDto> Items { get; init; } = new();
}

public record ResultadoItemConciliacionDto
{
    public Guid?     IdDetalle               { get; init; }
    public DateTime? FechaConduce            { get; init; }
    public string    NoConduce               { get; init; } = "";
    public string?   Producto                { get; init; }
    public string?   Mina                    { get; init; }
    public string?   Planta                  { get; init; }
    public decimal   CantidadDeclarada       { get; init; }
    public decimal   PrecioUnitario          { get; init; }
    public decimal   TotalReclamado          { get; init; }
    
    // Cruce con el sistema
    public Guid?     IdEntradaCamion         { get; init; }
    public string?   ProMov                  { get; init; }
    public string?   NumRecepcionOC          { get; init; }
    public int?      OrdenNumero             { get; init; }
    public Guid?     IdOrden                 { get; init; }
    public string?   ProductoEncontrado      { get; init; }
    public string?   PlantaEncontrada        { get; init; }
    public decimal?  CantidadSistema         { get; init; }
    public string?   UnidadSistema           { get; init; }
    public decimal?  PrecioSistema           { get; init; }
    public decimal?  TotalAprobado           { get; init; }
    
    // Resultados
    public string    EstadoCuadre            { get; init; } = "NO_CALIFICA"; // CALIFICA_PAGO, NO_CALIFICA, PENDIENTE_RECEPCION
    public string?   MotivoRechazo           { get; init; }
    public string    EstadoPago              { get; init; } = "PENDIENTE";   // PENDIENTE, CALIFICA_PAGO, RECHAZADO, APROBADO, PAGADO
    public DateTime? FechaPago               { get; init; }
    public string?   ReferenciaPago          { get; init; }
    public string?   Notas                   { get; init; }
}

public record ResultadoConciliacionDto
{
    public Guid?     IdConciliacion          { get; init; }
    public string?   NumeroConciliacion      { get; init; }
    public string?   IdSuplidor              { get; init; }
    public string    Suplidor                { get; init; } = "";
    public DateTime  FechaCarga              { get; init; } = DateTime.Now;
    public string?   Usuario                 { get; init; }
    public string?   NombreArchivo           { get; init; }
    public int       TotalConduces           { get; init; }
    public int       TotalCalifican          { get; init; }
    public int       TotalRechazados         { get; init; }
    public int       TotalPendientes         { get; init; }
    public decimal   MontoTotalReclamado     { get; init; }
    public decimal   MontoTotalCalifica      { get; init; }
    public string    Status                  { get; init; } = "REVISADO";
    public DateTime? FechaAprobacion         { get; init; }
    public string?   UsuarioAprobacion       { get; init; }
    public string?   Notas                   { get; init; }
    public List<ResultadoItemConciliacionDto> Items { get; init; } = new();
}

public record GuardarConciliacionRequest
{
    public string?   IdSuplidor              { get; init; }
    public string    Suplidor                { get; init; } = "";
    public string?   NombreArchivo           { get; init; }
    public string?   Notas                   { get; init; }
    public List<ResultadoItemConciliacionDto> Items { get; init; } = new();
}

public record LoteConciliacionDto
{
    public Guid      IdConciliacion          { get; init; }
    public string    NumeroConciliacion      { get; init; } = "";
    public string?   IdSuplidor              { get; init; }
    public string    Suplidor                { get; init; } = "";
    public DateTime  FechaCarga              { get; init; }
    public string    Usuario                 { get; init; } = "";
    public string?   NombreArchivo           { get; init; }
    public int       TotalConduces           { get; init; }
    public int       TotalCalifican          { get; init; }
    public int       TotalRechazados         { get; init; }
    public int       TotalPendientes         { get; init; }
    public decimal   MontoTotalReclamado     { get; init; }
    public decimal   MontoTotalCalifica      { get; init; }
    public string    Status                  { get; init; } = "";
    public DateTime? FechaAprobacion         { get; init; }
    public string?   UsuarioAprobacion       { get; init; }
    public string?   Notas                   { get; init; }
}

public record ActualizarEstadoPagoRequest
{
    public string    NuevoEstadoPago         { get; init; } = ""; // APROBADO, PAGADO, RECHAZADO, PENDIENTE
    public string?   ReferenciaPago          { get; init; }
    public string?   Notas                   { get; init; }
    public List<Guid>? IdsDetalle            { get; init; }
}
