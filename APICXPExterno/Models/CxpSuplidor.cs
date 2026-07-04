using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace CxpApi.Models;

[Table("cxpsuplidores")]
public class CxpSuplidor
{
    [Key]
    public int IdSuplidor { get; set; }
    
    [MaxLength(200)]
    public string? Nombre { get; set; }
    
    [MaxLength(20)]
    public string? RNC { get; set; }
    
    [MaxLength(500)]
    public string? Direccion { get; set; }
    
    [MaxLength(50)]
    public string? Telefono1 { get; set; }
    
    [MaxLength(100)]
    public string? EMail { get; set; }
    
    public int? DiasCredito { get; set; }
    
    [Column(TypeName = "decimal(18,2)")]
    public decimal? LimiteCredito { get; set; }
    
    public int? TipoImpuesto { get; set; }
    
    public int? IdMoneda { get; set; }
    
    [MaxLength(1)]
    public string? PedirNCF { get; set; }
    
    [MaxLength(50)]
    public string? FormaPago { get; set; }
    
    [MaxLength(50)]
    public string? Grupo { get; set; }
    
    public bool? Estatus { get; set; }
    
    public bool? MostrarEnCXP { get; set; }
}
