using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using CxpApi.Data;
using CxpApi.Models;
using System.Security.Claims;
using Azure;
using Azure.AI.FormRecognizer.DocumentAnalysis;

namespace CxpApi.Controllers;

public class FacturaRequest
{
    public int IdSuplidor { get; set; }
    public DateTime FechaEmision { get; set; }
    public DateTime? Vencimiento { get; set; }
    public string? Referencia { get; set; }
    public string? CompFiscal { get; set; }
    public string? Concepto { get; set; }
    public decimal Valor { get; set; }
    public decimal MontoImpuestos { get; set; }
    public decimal Total { get; set; }
    public string? RNC { get; set; }
    public string? Nombre { get; set; }
    public string? IdClasegasto { get; set; }
    public int IdMoneda { get; set; }
    public int IdPagoForma { get; set; }
    public bool EsServicio { get; set; }
    public string? FotoBase64 { get; set; }
    public string? Moneda { get; set; }
    public int idTrans { get; set; } = 1;
}

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class CxpDocumentoController : ControllerBase
{
    private readonly AppDbContext _erpDb;
    private readonly IConfiguration _config;

    public CxpDocumentoController(AppDbContext erpDb, IConfiguration config)
    {
        _erpDb = erpDb;
        _config = config;
    }

    [HttpPost]
    public async Task<IActionResult> CreateFactura([FromBody] FacturaRequest request)
    {
        var idUsuario = User.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value ?? "UNKNOWN";

        var nuevoDoc = new CxpDocumento
        {
            IdSuplidor = request.IdSuplidor,
            FechaEmision = request.FechaEmision,
            Vencimiento = request.Vencimiento,
            Referencia = request.Referencia,
            CompFiscal = request.CompFiscal,
            Concepto = request.Concepto,
            Valor = request.Valor,
            MontoImpuestos = request.MontoImpuestos,
            RNC = request.RNC,
            Nombre = request.Nombre,
            Usuario = idUsuario,
            // Campos auto-completados por el backend (Definidos en el Modelo per defecto)
            // GUIDDocumento = Guid.NewGuid(),
            // Fecha = DateTime.UtcNow,
            // FechaRegistro = DateTime.UtcNow,
            // Status = "A",
            // FechaStatus = DateTime.UtcNow,
            // Cancelado = false,
            // PendValidacion = true,
            // PendEnvioEcf = true
        };

        // Generar Guids y Fechas como lo espera Delphi
        var guidDoc = Guid.NewGuid();
        var fechaActual = DateTime.UtcNow;
        var rncDefinitivo = string.IsNullOrEmpty(request.RNC) ? "" : request.RNC;
        var nombreDefinitivo = string.IsNullOrEmpty(request.Nombre) ? "" : request.Nombre;
        var refDefinitiva = string.IsNullOrEmpty(request.Referencia) ? "" : request.Referencia;
        var ncfDefinitivo = string.IsNullOrEmpty(request.CompFiscal) ? "" : request.CompFiscal;
        var conceptoDefinitivo = string.IsNullOrEmpty(request.Concepto) ? "" : request.Concepto;

        try
        {
            await _erpDb.Database.OpenConnectionAsync();
            var connection = _erpDb.Database.GetDbConnection();

            using var transaction = connection.BeginTransaction();
            var command = connection.CreateCommand();
            command.Transaction = transaction;

            var addParam = (string name, object? value) => {
                var p = command.CreateParameter();
                p.ParameterName = name;
                p.Value = value ?? DBNull.Value;
                command.Parameters.Add(p);
            };

            // 1. DUPLICATE CHECK (Prevenir duplicados por NCF o por Referencia)
            if (!string.IsNullOrEmpty(refDefinitiva) || !string.IsNullOrEmpty(ncfDefinitivo))
            {
                var conditions = new List<string>();
                if (!string.IsNullOrEmpty(ncfDefinitivo)) conditions.Add("CompFiscal = @CheckNCF");
                if (!string.IsNullOrEmpty(refDefinitiva)) conditions.Add("Referencia = @CheckRef");

                command.CommandText = $"SELECT TOP 1 1 FROM cxpDocumentos WHERE idSuplidor = @CheckIdSup AND ({string.Join(" OR ", conditions)}) AND Status <> 'C'";
                addParam("@CheckIdSup", request.IdSuplidor);
                if (!string.IsNullOrEmpty(ncfDefinitivo)) addParam("@CheckNCF", ncfDefinitivo);
                if (!string.IsNullOrEmpty(refDefinitiva)) addParam("@CheckRef", refDefinitiva);

                var exists = await command.ExecuteScalarAsync();
                if (exists != null && exists != DBNull.Value)
                {
                    return BadRequest(new { success = false, mensaje = "El Comprobante Fiscal (NCF) o el Número de Factura ya fue registrado para este suplidor." });
                }
                command.Parameters.Clear();
            }

            // --- NUEVAS CONSULTAS DINAMICAS ---
            
            // 2.1 Cuenta del Suplidor (idCuenta)
            command.CommandText = "SELECT idcuenta FROM cxpSuplidorCuenta WHERE idSuplidor = @IdSuplidorCta";
            addParam("@IdSuplidorCta", request.IdSuplidor);
            var idCuentaResult = await command.ExecuteScalarAsync();
            string finalIdCuenta = (idCuentaResult != null && idCuentaResult != DBNull.Value) ? idCuentaResult.ToString()! : "2000201";
            command.Parameters.Clear();

            // 2.2 Tipo de Identificacion (idTipoIdentificacion)
            string tipoIdentStr = (!string.IsNullOrEmpty(rncDefinitivo) && rncDefinitivo.Length == 11) ? "Cedula" : "RNC";
            command.CommandText = "SELECT idTipoIdentificacion FROM TipoIdentificacion WHERE TipoIdentificacion = @TipoIdent";
            addParam("@TipoIdent", tipoIdentStr);
            var tipoIdentResult = await command.ExecuteScalarAsync();
            string finalTipoIdentificacion = (tipoIdentResult != null && tipoIdentResult != DBNull.Value) ? tipoIdentResult.ToString()! : "02";
            command.Parameters.Clear();

            // 2.3 Moneda (idMoneda)
            int finalIdMoneda = request.IdMoneda; 
            if (!string.IsNullOrEmpty(request.Moneda)) 
            {
                command.CommandText = "SELECT idMoneda FROM Moneda WHERE moneda = @MonedaStr";
                addParam("@MonedaStr", request.Moneda);
                var monedaResult = await command.ExecuteScalarAsync();
                if (monedaResult != null && monedaResult != DBNull.Value)
                {
                    finalIdMoneda = Convert.ToInt32(monedaResult);
                }
                command.Parameters.Clear();
            }

            // 2.4 Clase de Gasto (idClaseGasto)
            command.CommandText = "SELECT valor FROM Defaults WHERE Clave = 'ClaseGasto'";
            var claseGastoResult = await command.ExecuteScalarAsync();
            string finalIdClaseGasto = (claseGastoResult != null && claseGastoResult != DBNull.Value) ? claseGastoResult.ToString()! : "01";
            
            if (!string.IsNullOrEmpty(request.IdClasegasto)) 
            {
                finalIdClaseGasto = request.IdClasegasto;
            }
            command.Parameters.Clear();

            // 2. INSERT FACTURA
            command.CommandText = @"
                INSERT INTO cxpDocumentos (
                    idTrans, Fecha, idSuplidor, Referencia, Valor, 
                    MontoImpuestos, MontoDescuento, MontoRetenciones, Concepto, 
                    idMoneda, CodifManual, Status, FechaStatus, idCuenta, 
                    TipoDocOrigen, DocOrigen, Dias, MostrarenCxP, BienesServicio,
                    NotaAdicional, idAuxiliar, CompFiscal, GUIDDocumento, 
                    idTipoIdentificacion, idClaseGasto, Tasa, TipoAbono, 
                    RNC, Nombre, Vencimiento, FechaEmision, TipoGasto,
                    idPagoForma, montoFacturadoBienes, montoFacturadoServicios, 
                    MontoItbisCosto, MontoIsc, OtrosImpuestos, PropinaLegal,
                    idPartida, OrdenCompra, CuentaDestino, BancoDestino
                ) 
                OUTPUT INSERTED.idDocumento
                VALUES (
                    @IdTrans, @Fecha, @IdSuplidor, @Referencia, @Valor, 
                    @MontoImpuestos, 0, 0, @Concepto, 
                    @IdMoneda, 0, 'A', @FechaStatus, @IdCuenta, 
                    '', 0, 0, 0, 1,
                    '', '', @CompFiscal, @GUIDDocumento, 
                    @IdTipoIdentificacion, @IdClasegasto, 1, '1', 
                    @RNC, @Nombre, @Vencimiento, @FechaEmision, 'COSTO',
                    @IdPagoForma, @MontoFBienes, @MontoFServicios, 
                    0, 0, 0, 0,
                    '', '', '', ''
                )";

            addParam("@IdTrans", request.idTrans);
            addParam("@Fecha", request.FechaEmision.Date);
            addParam("@FechaStatus", fechaActual);
            addParam("@IdSuplidor", request.IdSuplidor);
            addParam("@Referencia", refDefinitiva);
            addParam("@Valor", request.Valor);
            addParam("@MontoImpuestos", request.MontoImpuestos);
            addParam("@Concepto", conceptoDefinitivo);
            addParam("@IdMoneda", finalIdMoneda);
            addParam("@CompFiscal", ncfDefinitivo);
            addParam("@GUIDDocumento", guidDoc);
            addParam("@IdClasegasto", finalIdClaseGasto);
            addParam("@IdCuenta", finalIdCuenta);
            addParam("@IdTipoIdentificacion", finalTipoIdentificacion);
            addParam("@RNC", rncDefinitivo);
            addParam("@Nombre", nombreDefinitivo);
            addParam("@Vencimiento", request.Vencimiento.HasValue ? request.Vencimiento.Value.Date : request.FechaEmision.Date);
            addParam("@FechaEmision", request.FechaEmision.Date);
            addParam("@IdPagoForma", request.IdPagoForma);
            
            // Logica Bienes/Servicios Distribuido
            if (request.EsServicio)
            {
                addParam("@MontoFBienes", 0m);
                addParam("@MontoFServicios", request.Valor);
            }
            else
            {
                addParam("@MontoFBienes", request.Valor);
                addParam("@MontoFServicios", 0m);
            }

            var resultId = await command.ExecuteScalarAsync();
            var finalId = Convert.ToInt32(resultId);

            // 3. INSERT IMAGEN (Si existe)
            if (!string.IsNullOrEmpty(request.FotoBase64))
            {
                // Limpiar prefijo data:image/xxx;base64, si el frontend lo envió
                var base64Data = request.FotoBase64;
                if (base64Data.Contains(","))
                {
                    base64Data = base64Data.Substring(base64Data.IndexOf(",") + 1);
                }

                byte[] imageBytes = Convert.FromBase64String(base64Data);

                var imgCommand = connection.CreateCommand();
                imgCommand.Transaction = transaction;
                imgCommand.CommandText = @"
                    INSERT INTO ImgImagen (
                        idImagen, idDocumento, imagen, Fecha, TipoDoc, esPDF
                    ) VALUES (
                        @IdImagen, @IdDocumento, @Imagen, @FechaImg, 'FacturaCXP', 0
                    )";

                var addImgParam = (string name, object? value) => {
                    var p = imgCommand.CreateParameter();
                    p.ParameterName = name;
                    p.Value = value ?? DBNull.Value;
                    imgCommand.Parameters.Add(p);
                };

                addImgParam("@IdImagen", Guid.NewGuid());
                addImgParam("@IdDocumento", guidDoc);
                addImgParam("@Imagen", imageBytes);
                addImgParam("@FechaImg", DateTime.Now);

                await imgCommand.ExecuteNonQueryAsync();
            }

            transaction.Commit();

            return Ok(new 
            {
                success = true,
                mensaje = "Factura registrada exitosamente con SQL Directo.",
                idDocumento = finalId,
                guidDocumento = guidDoc,
                databaseDestino = connection.Database,
                serverDestino = connection.DataSource
            });
        }
        catch (Exception ex)
        {
            var msg = ex.InnerException?.Message ?? ex.Message;
            return BadRequest(new { mensaje = $"Error SQL directo al registrar: {msg}" });
        }
    }

    [HttpPost("escanear")]
    public async Task<IActionResult> EscanearFactura([FromBody] OcrRequest request)
    {
        if (string.IsNullOrEmpty(request.FotoBase64))
        {
            return BadRequest(new { success = false, mensaje = "No se recibió ninguna imagen." });
        }

        try
        {
            var base64Data = request.FotoBase64;
            if (base64Data.Contains(","))
            {
                base64Data = base64Data.Split(',')[1];
            }

            var endpoint = _config["AzureOcr:Endpoint"];
            var key = _config["AzureOcr:Key"];

            if (string.IsNullOrEmpty(endpoint) || string.IsNullOrEmpty(key))
            {
                return BadRequest(new { success = false, mensaje = "Credenciales de Azure OCR no configuradas en el servidor." });
            }

            var credential = new AzureKeyCredential(key);
            var client = new DocumentAnalysisClient(new Uri(endpoint), credential);

            var bytes = Convert.FromBase64String(base64Data);
            using var stream = new MemoryStream(bytes);

            // Using prebuilt-invoice to accurately read RNC/NCF logic
            var operation = await client.AnalyzeDocumentAsync(WaitUntil.Completed, "prebuilt-invoice", stream);
            var result = operation.Value;

            if (result.Documents.Count == 0)
            {
                return BadRequest(new { success = false, mensaje = "No se pudo detectar ninguna factura en la imagen." });
            }

            var invoice = result.Documents[0];

            string rnc = "";
            string ncf = "";
            string referencia = "";
            DateTime? fecha = null;
            decimal total = 0;
            decimal itbis = 0;
            decimal subtotal = 0;

            if (invoice.Fields.TryGetValue("VendorTaxId", out var vendorTaxId))
                rnc = vendorTaxId.Content;

            var ncfRegex = new System.Text.RegularExpressions.Regex(@"\b[A-Za-z](?:\d{10}|\d{12})\b");
            if (!string.IsNullOrEmpty(result.Content))
            {
                var ncfMatch = ncfRegex.Match(result.Content);
                if (ncfMatch.Success)
                {
                    ncf = ncfMatch.Value.ToUpper();
                }
            }

            if (invoice.Fields.TryGetValue("InvoiceId", out var invoiceId))
            {
                var invoiceVal = invoiceId.Content;
                if (string.IsNullOrEmpty(ncf) && ncfRegex.IsMatch(invoiceVal))
                {
                    ncf = invoiceVal.ToUpper();
                }
                else if (invoiceVal != ncf)
                {
                    referencia = invoiceVal;
                }
            }

            if (invoice.Fields.TryGetValue("InvoiceDate", out var invoiceDate))
            {
                try 
                { 
                    var d = invoiceDate.Value.AsDate();
                    fecha = d.DateTime;
                } 
                catch 
                { 
                    if (!string.IsNullOrEmpty(invoiceDate.Content) && DateTime.TryParse(invoiceDate.Content, out var parsed))
                    {
                        fecha = parsed;
                    }
                }
            }

            if (invoice.Fields.TryGetValue("SubTotal", out var docSubTotal))
            {
                if (docSubTotal.ExpectedFieldType == Azure.AI.FormRecognizer.DocumentAnalysis.DocumentFieldType.Currency)
                {
                    try { subtotal = (decimal)docSubTotal.Value.AsCurrency().Amount; } catch { }
                }
                else
                {
                    try { subtotal = (decimal)docSubTotal.Value.AsDouble(); }
                    catch { if (!string.IsNullOrEmpty(docSubTotal.Content)) decimal.TryParse(docSubTotal.Content.Replace("$", "").Replace(",", ""), out subtotal); }
                }
            }

            string monedaOcr = "RD$";
            if (invoice.Fields.TryGetValue("InvoiceTotal", out var invoiceTotal))
            {
                if (invoiceTotal.ExpectedFieldType == Azure.AI.FormRecognizer.DocumentAnalysis.DocumentFieldType.Currency)
                {
                    try {
                        var cur = invoiceTotal.Value.AsCurrency();
                        total = (decimal)cur.Amount;
                        if (cur.Symbol == "USD" || cur.Symbol == "US$" || cur.Symbol == "$") monedaOcr = "US$";
                    } catch { } 
                }
                else
                {
                    try { total = (decimal)invoiceTotal.Value.AsDouble(); }
                    catch { if (!string.IsNullOrEmpty(invoiceTotal.Content)) decimal.TryParse(invoiceTotal.Content.Replace("$", "").Replace(",", ""), out total); }
                }
            }

            if (invoice.Fields.TryGetValue("TotalTax", out var totalTax))
            {
                try 
                { 
                    itbis = (decimal)totalTax.Value.AsDouble(); 
                }
                catch 
                { 
                    if (!string.IsNullOrEmpty(totalTax.Content)) decimal.TryParse(totalTax.Content.Replace("$", "").Replace(",", ""), out itbis); 
                }
            }

            // ESTRATEGIA DE RESPALDO: Iterar sobre KeyValuePairs y Líneas si faltan valores
            if ((total == 0 || itbis == 0 || subtotal == 0) && result.KeyValuePairs != null)
            {
                foreach (var kvp in result.KeyValuePairs)
                {
                    if (kvp.Key == null || kvp.Value == null) continue;
                    
                    var keyText = kvp.Key.Content.ToLowerInvariant().Replace(" ", "").Replace(".", "");
                    var valText = kvp.Value.Content.Replace("$", "").Replace(",", "").Trim();
                    
                    if (!decimal.TryParse(valText, out var parsedVal)) continue;

                    if (itbis == 0 && (keyText.Contains("itbis") || keyText.Contains("impuesto") || keyText.Contains("tax")))
                        itbis = parsedVal;
                    else if (subtotal == 0 && (keyText.Contains("subtotal") || keyText.Contains("sub-total") || keyText.Contains("montogravado") || keyText.Contains("valor")))
                        subtotal = parsedVal;
                    else if (keyText.Contains("totalapagar") || keyText.Contains("grantotal") || keyText.Equals("total") || keyText.Contains("montoapagar"))
                        total = Math.Max(total, parsedVal);
                }
            }

            // SUPER ESTRATEGIA DE RESPALDO: Iterar sobre lineas de texto crudo (Ya que a veces Prebuilt-Invoice no arroja KeyValuePairs)
            if ((total == 0 || itbis == 0 || subtotal == 0 || result.KeyValuePairs != null) && result.Pages != null)
            {
                bool foundTotalItbis = false;
                foreach (var page in result.Pages)
                {
                    if (page.Lines == null) continue;
                    var lines = page.Lines.ToList();
                    for (int i = 0; i < lines.Count; i++)
                    {
                        var txt = lines[i].Content.ToLowerInvariant().Replace(" ", "").Replace(".", "");
                        var tokens = lines[i].Content.Split(' ');
                        
                        var numbers = new List<decimal>();
                        for(int j = 0; j < tokens.Length; j++)
                        {
                            var t = tokens[j];
                            if (t == "%" || t.EndsWith("%") || (j + 1 < tokens.Length && tokens[j+1] == "%")) continue;
                            
                            var cleanT = t.Replace("$", "").Replace(",", "").Trim();
                            if (decimal.TryParse(cleanT, out var n) && n > 0) numbers.Add(n);
                        }

                        decimal actVal = 0;
                        if (numbers.Count > 0)
                        {
                            actVal = (txt.Contains("totalapagar") || txt.Contains("grantotal")) ? numbers.Max() : numbers.Last();
                        }
                        else if (i + 1 < lines.Count)
                        {
                            var nextTokens = lines[i+1].Content.Split(' ');
                            var nextNumbers = new List<decimal>();
                            for(int j = 0; j < nextTokens.Length; j++)
                            {
                                var t = nextTokens[j];
                                if (t == "%" || t.EndsWith("%") || (j + 1 < nextTokens.Length && nextTokens[j+1] == "%")) continue;
                                var cleanT = t.Replace("$", "").Replace(",", "").Trim();
                                if (decimal.TryParse(cleanT, out var n) && n > 0) nextNumbers.Add(n);
                            }
                            if (nextNumbers.Count > 0)
                            {
                                actVal = (txt.Contains("totalapagar") || txt.Contains("grantotal")) ? nextNumbers.Max() : nextNumbers.Last();
                            }
                        }

                        if (actVal > 0)
                        {
                            bool isTotalItbis = txt.Contains("totalitbis") || txt.Contains("totalimpuesto");
                            if ((itbis == 0 || (isTotalItbis && !foundTotalItbis)) && (isTotalItbis || txt.Equals("itbis") || txt.Contains("impuesto") || (txt.Contains("itbis") && !txt.Contains("totalapagar"))))
                            {
                                itbis = actVal;
                                if (isTotalItbis) foundTotalItbis = true;
                            }
                            else if (subtotal == 0 && (txt.Contains("subtotal") || txt.Contains("montogravado"))) 
                            {
                                subtotal = actVal;
                            }
                            else if (txt.Contains("totalapagar") || txt.Contains("grantotal") || txt.Equals("total")) 
                            {
                                total = Math.Max(total, actVal);
                            }
                        }
                    }
                }
            }

            // --- SANITY CHECKS Y CORRECIONES MATEMÁTICAS ---
            // Regla 1: El Total NUNCA puede ser igual al ITBIS
            if (total > 0 && itbis > 0 && total == itbis)
            {
                decimal maxTotalDetectado = 0;
                
                // Opción B: Búsqueda por coordenada Y (Misma fila)
                if (result.Pages != null)
                {
                    foreach (var page in result.Pages)
                    {
                        if (page.Lines == null) continue;
                        
                        var lineTotals = page.Lines.Where(l => 
                            l.Content.ToLowerInvariant().Replace(" ", "").Contains("totalapagar") || 
                            l.Content.ToLowerInvariant().Replace(" ", "").Contains("grantotal") ||
                            l.Content.ToLowerInvariant().Trim() == "total"
                        ).ToList();

                        foreach (var lineTotal in lineTotals)
                        {
                            if (lineTotal.BoundingPolygon == null || lineTotal.BoundingPolygon.Count < 4) continue;
                            
                            var yMin = lineTotal.BoundingPolygon.Min(p => p.Y);
                            var yMax = lineTotal.BoundingPolygon.Max(p => p.Y);
                            var height = yMax - yMin;
                            var yCenter = yMin + (height / 2);
                            
                            if (page.Words != null)
                            {
                                foreach (var word in page.Words)
                                {
                                    if (word.BoundingPolygon == null || word.BoundingPolygon.Count < 4) continue;
                                    
                                    var wYMin = word.BoundingPolygon.Min(p => p.Y);
                                    var wYMax = word.BoundingPolygon.Max(p => p.Y);
                                    var wCenter = wYMin + ((wYMax - wYMin) / 2);
                                    
                                    // Tolerancia razonable en Y (un alto entero de la linea)
                                    if (Math.Abs(wCenter - yCenter) <= height)
                                    {
                                        var cleanW = word.Content.Replace("$", "").Replace(",", "").Trim();
                                        if (decimal.TryParse(cleanW, out var n) && n > maxTotalDetectado)
                                        {
                                            maxTotalDetectado = n;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                if (maxTotalDetectado > itbis)
                {
                    total = maxTotalDetectado;
                }
                else if (subtotal > 0)
                {
                    // Opción A: Suma matemática
                    total = subtotal + itbis;
                }
                else 
                {
                    // Forzamos 0 para evitar el valor errado
                    total = 0; 
                }
            }

            var response = new OcrResponse
            {
                Success = true,
                Mensaje = "Extracción completada con Azure AI",
                RNC = rnc,
                NCF = ncf,
                Referencia = referencia,
                Fecha = fecha,
                TotalBienes = Math.Round(total, 2),
                SubTotal = Math.Round(subtotal, 2),
                TotalServicios = 0.00m,
                Itbis = Math.Round(itbis, 2),
                Moneda = monedaOcr
            };

            return Ok(response);
        }
        catch (Exception ex)
        {
            var msg = ex.InnerException?.Message ?? ex.Message;
            return BadRequest(new { success = false, mensaje = $"Error de OCR en Azure: {msg}" });
        }
    }

    [HttpGet("registradas")]
    public async Task<IActionResult> GetFacturasRegistradas([FromQuery] string? buscar)
    {
        var idUsuario = User.FindFirst(System.IdentityModel.Tokens.Jwt.JwtRegisteredClaimNames.Sub)?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        if (string.IsNullOrEmpty(idUsuario))
        {
            // Fallback for cases where it might not be securely mapped, though Authorize should catch it
            idUsuario = "UNKNOWN"; 
        }

        try
        {
            await _erpDb.Database.OpenConnectionAsync();
            var connection = _erpDb.Database.GetDbConnection();

            var command = connection.CreateCommand();
            
            string whereFilter = "";
            if (!string.IsNullOrWhiteSpace(buscar))
            {
                whereFilter = "WHERE d.Nombre LIKE '%' + @Buscar + '%' OR d.CompFiscal LIKE '%' + @Buscar + '%' OR d.RNC LIKE '%' + @Buscar + '%' OR d.Referencia LIKE '%' + @Buscar + '%'";
                var pSearch = command.CreateParameter();
                pSearch.ParameterName = "@Buscar";
                pSearch.Value = buscar.Trim();
                command.Parameters.Add(pSearch);
            }

            command.CommandText = $@"
                SELECT TOP 50
                    d.idDocumento,
                    d.GUIDDocumento,
                    d.FechaEmision,
                    d.CompFiscal,
                    d.Concepto,
                    (COALESCE(d.montoFacturadoBienes, 0) + COALESCE(d.montoFacturadoServicios, 0) + COALESCE(d.MontoImpuestos, 0)) as Total,
                    d.RNC,
                    d.Nombre,
                    CASE WHEN i.idDocumento IS NOT NULL THEN 1 ELSE 0 END as TieneImagen
                FROM cxpDocumentos d
                LEFT JOIN ImgImagen i ON d.GUIDDocumento = i.idDocumento
                {whereFilter}
                ORDER BY d.Fecha DESC
            ";
            
            var param = command.CreateParameter();
            param.ParameterName = "@Usuario";
            param.Value = idUsuario;
            command.Parameters.Add(param);

            var facturas = new List<object>();

            using (var reader = await command.ExecuteReaderAsync())
            {
                while (await reader.ReadAsync())
                {
                    facturas.Add(new
                    {
                        idDocumento = reader["idDocumento"],
                        guidDocumento = reader["GUIDDocumento"],
                        fechaEmision = reader["FechaEmision"],
                        compFiscal = reader["CompFiscal"]?.ToString(),
                        concepto = reader["Concepto"]?.ToString(),
                        total = reader["Total"],
                        rnc = reader["RNC"]?.ToString(),
                        nombre = reader["Nombre"]?.ToString(),
                        tieneImagen = Convert.ToBoolean(reader["TieneImagen"])
                    });
                }
            }

            return Ok(facturas);
        }
        catch (Exception ex)
        {
            return BadRequest(new { mensaje = "Error al obtener las facturas registradas.", detalle = ex.Message });
        }
    }

    [HttpGet("{guid}/imagen")]
    public async Task<IActionResult> GetImagenFactura(Guid guid)
    {
        try
        {
            await _erpDb.Database.OpenConnectionAsync();
            var connection = _erpDb.Database.GetDbConnection();

            var command = connection.CreateCommand();
            command.CommandText = "SELECT imagen FROM ImgImagen WHERE idDocumento = @IdDocumento";
            
            var param = command.CreateParameter();
            param.ParameterName = "@IdDocumento";
            param.Value = guid;
            command.Parameters.Add(param);

            var imageObj = await command.ExecuteScalarAsync();

            if (imageObj != null && imageObj != DBNull.Value)
            {
                byte[] imageBytes = (byte[])imageObj;
                string base64String = Convert.ToBase64String(imageBytes);
                return Ok(new { success = true, imagenBase64 = base64String });
            }

            return NotFound(new { success = false, mensaje = "Imagen no encontrada." });
        }
        catch (Exception ex)
        {
            return BadRequest(new { success = false, mensaje = "Error al obtener la imagen.", detalle = ex.Message });
        }
    }
    
    [HttpGet("tables")]
    [AllowAnonymous]
    public async Task<IActionResult> GetTables()
    {
        var tables = new List<string>();
        using (var command = _erpDb.Database.GetDbConnection().CreateCommand())
        {
            // Busca codigo fuente de triggers para cxpDocumentos
            command.CommandText = @"
                SELECT m.definition 
                FROM sys.triggers t 
                INNER JOIN sys.sql_modules m ON t.object_id = m.object_id 
                WHERE t.parent_id = OBJECT_ID('cxpDocumentos')";
            _erpDb.Database.OpenConnection();
            using (var result = await command.ExecuteReaderAsync())
            {
                while (await result.ReadAsync())
                {
                    tables.Add(result.GetString(0));
                }
            }
        }
        return Ok(tables);
    }

    [HttpGet("schema")]
    [AllowAnonymous]
    public async Task<IActionResult> GetSchema()
    {
        var schema = new List<object>();
        using (var command = _erpDb.Database.GetDbConnection().CreateCommand())
        {
            command.CommandText = "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'cxpDocumentos'";
            _erpDb.Database.OpenConnection();
            using (var result = await command.ExecuteReaderAsync())
            {
                while (await result.ReadAsync())
                {
                    schema.Add(new
                    {
                        Column = result.GetString(0),
                        Type = result.GetString(1)
                    });
                }
            }
        }
        return Ok(schema);
    }
}
