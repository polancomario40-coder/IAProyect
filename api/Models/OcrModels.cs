using System;

namespace CxpApi.Models;

public class OcrRequest
{
    public string? FotoBase64 { get; set; }
}

public class OcrResponse
{
    public bool Success { get; set; }
    public string? Mensaje { get; set; }
    public string? RNC { get; set; }
    public string? NCF { get; set; }
    public DateTime? Fecha { get; set; }
    public decimal TotalBienes { get; set; }
    public decimal TotalServicios { get; set; }
}
