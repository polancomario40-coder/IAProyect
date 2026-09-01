using System.ComponentModel.DataAnnotations;

namespace CxpApi.Models;

public class CxpFacturaExternaDto
{
    [Required]
    public string BaseDatos { get; set; } = string.Empty;

    [Required(AllowEmptyStrings = true)]
    public string RncCompania { get; set; } = string.Empty;

    [Required]
    public string RncSuplidor { get; set; } = string.Empty;

    public string? NombreSuplidor { get; set; }
    public string? Direccion { get; set; }
    public string? Ciudad { get; set; }
    public string? Provincia { get; set; }
    public string? Pais { get; set; }

    [Required]
    public string Ncf { get; set; } = string.Empty;

    [Required]
    public DateTime FechaFactura { get; set; }

    [Required]
    public decimal Subtotal { get; set; }

    [Required]
    public decimal Itbis { get; set; }

    public decimal Propina { get; set; }
    public decimal Isc { get; set; }
    public decimal OtrosImpuestos { get; set; }
    public decimal ItbisAlCosto { get; set; }
    public bool EsServicio { get; set; }

    public int IdMoneda { get; set; } = 1;
    public string? Moneda { get; set; }

    [Required]
    public decimal Total { get; set; }
}
