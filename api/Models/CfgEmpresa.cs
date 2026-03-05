using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace CxpApi.Models;

[Table("cfgempresa")]
public class CfgEmpresa
{
    [Key]
    public Guid IdEmpresa { get; set; }
    
    [Required]
    [MaxLength(200)]
    public string Empresa { get; set; }
    
    [MaxLength(20)]
    public string RNC { get; set; }
    
    [Required]
    [MaxLength(50)]
    public string Servidor { get; set; }
    
    [Required]
    [MaxLength(50)]
    public string BaseDatos { get; set; }
    
    public bool Trusted { get; set; }
    
    [MaxLength(50)]
    public string? UserId { get; set; }
    
    [MaxLength(100)]
    public string? UserPwd { get; set; }
    
    public bool Encriptada { get; set; }
    
    public bool Activa { get; set; }
    
    public bool AccesoWeb { get; set; }
}
