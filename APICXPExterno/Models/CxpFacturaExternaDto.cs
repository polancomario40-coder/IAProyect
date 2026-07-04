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

    [Required]
    public string Ncf { get; set; } = string.Empty;

    [Required]
    public DateTime FechaFactura { get; set; }

    [Required]
    public decimal Subtotal { get; set; }

    [Required]
    public decimal Itbis { get; set; }

    [Required]
    public decimal Total { get; set; }
}
